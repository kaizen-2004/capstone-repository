# Google Colab: Face-Mask Classifier Training and ONNX Export

This guide gives a ready-to-run, cell-by-cell Google Colab workflow to train a
face-crop mask classifier (`mask` vs `no_mask`) and export it to ONNX for your
backend.

## Expected output artifacts

- `mask_detection.onnx`
- `mask_labels.json`
- `mask_thresholds.json`
- `training_metrics.json`

Store these under your project, for example:
`backend/storage/models/face_mask/`

---

## Cell 1 - Runtime and dependency setup

```python
!nvidia-smi
!pip -q install --upgrade pip
!pip -q install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
!pip -q install onnx onnxruntime opencv-python scikit-learn matplotlib pandas tqdm
```

---

## Cell 2 - Mount Google Drive and define project folders

```python
from google.colab import drive
drive.mount('/content/drive')

from pathlib import Path

# Change this to your preferred Drive folder
ROOT = Path('/content/drive/MyDrive/thesis_mask_training')
DATA_ROOT = ROOT / 'dataset'
OUTPUT_ROOT = ROOT / 'outputs'
CKPT_ROOT = ROOT / 'checkpoints'

for p in [DATA_ROOT, OUTPUT_ROOT, CKPT_ROOT]:
    p.mkdir(parents=True, exist_ok=True)

print('ROOT:', ROOT)
print('DATA_ROOT:', DATA_ROOT)
print('OUTPUT_ROOT:', OUTPUT_ROOT)
print('CKPT_ROOT:', CKPT_ROOT)
```

---

## Cell 3 - Dataset layout check

Use this directory structure:

- `dataset/train/mask`
- `dataset/train/no_mask`
- `dataset/val/mask`
- `dataset/val/no_mask`
- `dataset/test/mask`
- `dataset/test/no_mask`

```python
from pathlib import Path

required = [
    DATA_ROOT / 'train' / 'mask',
    DATA_ROOT / 'train' / 'no_mask',
    DATA_ROOT / 'val' / 'mask',
    DATA_ROOT / 'val' / 'no_mask',
    DATA_ROOT / 'test' / 'mask',
    DATA_ROOT / 'test' / 'no_mask',
]

missing = [str(p) for p in required if not p.exists()]
if missing:
    print('Missing folders:')
    for m in missing:
        print('-', m)
else:
    print('All required folders exist.')

for split in ['train', 'val', 'test']:
    for cls in ['mask', 'no_mask']:
        p = DATA_ROOT / split / cls
        if p.exists():
            count = len(list(p.glob('*')))
            print(f'{split:5s} {cls:8s}: {count}')
```

---

## Cell 4 - Training configuration

```python
import json
import random
import numpy as np
import torch

SEED = 42
IMG_SIZE = 224
BATCH_SIZE = 64
EPOCHS = 25
LR = 3e-4
WEIGHT_DECAY = 1e-4
PATIENCE = 5
NUM_WORKERS = 2

LABELS = ['mask', 'no_mask']
CLASS_TO_IDX = {c: i for i, c in enumerate(LABELS)}

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
print('DEVICE:', DEVICE)
```

---

## Cell 5 - Dataloaders with realistic augmentation

```python
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

train_tfms = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.15, hue=0.02),
    transforms.RandomRotation(degrees=8),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

eval_tfms = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

train_ds = datasets.ImageFolder(DATA_ROOT / 'train', transform=train_tfms)
val_ds = datasets.ImageFolder(DATA_ROOT / 'val', transform=eval_tfms)
test_ds = datasets.ImageFolder(DATA_ROOT / 'test', transform=eval_tfms)

print('Detected classes:', train_ds.classes)
if train_ds.classes != LABELS:
    raise ValueError(f'Expected class order {LABELS}, got {train_ds.classes}')

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=NUM_WORKERS, pin_memory=True)
val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS, pin_memory=True)
test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS, pin_memory=True)

print('Train/Val/Test sizes:', len(train_ds), len(val_ds), len(test_ds))
```

---

## Cell 6 - Model, optimizer, loss

```python
import torch.nn as nn
import torchvision.models as models

model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
in_features = model.classifier[-1].in_features
model.classifier[-1] = nn.Linear(in_features, len(LABELS))
model = model.to(DEVICE)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

print(model.__class__.__name__)
```

---

## Cell 7 - Train/validate loop with early stopping

```python
from sklearn.metrics import f1_score
from tqdm import tqdm
import copy
import time

def run_epoch(model, loader, train=True):
    if train:
        model.train()
    else:
        model.eval()

    running_loss = 0.0
    y_true = []
    y_pred = []

    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for xb, yb in tqdm(loader, leave=False):
            xb = xb.to(DEVICE, non_blocking=True)
            yb = yb.to(DEVICE, non_blocking=True)

            if train:
                optimizer.zero_grad(set_to_none=True)

            logits = model(xb)
            loss = criterion(logits, yb)

            if train:
                loss.backward()
                optimizer.step()

            running_loss += loss.item() * xb.size(0)
            preds = torch.argmax(logits, dim=1)
            y_true.extend(yb.detach().cpu().numpy().tolist())
            y_pred.extend(preds.detach().cpu().numpy().tolist())

    epoch_loss = running_loss / len(loader.dataset)
    epoch_f1 = f1_score(y_true, y_pred, average='macro')
    return epoch_loss, epoch_f1


best_state = None
best_val_f1 = -1.0
bad_epochs = 0
history = []

start = time.time()
for epoch in range(1, EPOCHS + 1):
    train_loss, train_f1 = run_epoch(model, train_loader, train=True)
    val_loss, val_f1 = run_epoch(model, val_loader, train=False)
    scheduler.step()

    history.append({
        'epoch': epoch,
        'train_loss': train_loss,
        'train_f1_macro': train_f1,
        'val_loss': val_loss,
        'val_f1_macro': val_f1,
        'lr': optimizer.param_groups[0]['lr'],
    })

    print(f"Epoch {epoch:02d} | train_loss={train_loss:.4f} train_f1={train_f1:.4f} | val_loss={val_loss:.4f} val_f1={val_f1:.4f}")

    if val_f1 > best_val_f1:
        best_val_f1 = val_f1
        best_state = copy.deepcopy(model.state_dict())
        bad_epochs = 0
        torch.save(best_state, CKPT_ROOT / 'best_model.pt')
    else:
        bad_epochs += 1
        if bad_epochs >= PATIENCE:
            print(f'Early stopping after {epoch} epochs.')
            break

elapsed = time.time() - start
print(f'Training done in {elapsed/60:.2f} min. Best val F1={best_val_f1:.4f}')

model.load_state_dict(best_state)
```

---

## Cell 8 - Test metrics and confusion matrix

```python
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

model.eval()
y_true, y_pred, y_prob_mask = [], [], []

with torch.no_grad():
    for xb, yb in test_loader:
        xb = xb.to(DEVICE, non_blocking=True)
        logits = model(xb)
        probs = torch.softmax(logits, dim=1)
        preds = torch.argmax(probs, dim=1)

        y_true.extend(yb.numpy().tolist())
        y_pred.extend(preds.cpu().numpy().tolist())
        y_prob_mask.extend(probs[:, CLASS_TO_IDX['mask']].cpu().numpy().tolist())

print('Classification report:')
print(classification_report(y_true, y_pred, target_names=LABELS, digits=4))

cm = confusion_matrix(y_true, y_pred)
print('Confusion matrix:')
print(cm)
```

---

## Cell 9 - Threshold sweep for `mask` class

This chooses a practical confidence threshold for `mask` prediction, instead of
always using 0.5.

```python
from sklearn.metrics import precision_recall_fscore_support

y_true_np = np.array(y_true)
y_prob_mask_np = np.array(y_prob_mask)

best_thr = 0.5
best_mask_f1 = -1.0
rows = []

for thr in np.arange(0.30, 0.91, 0.02):
    pred_mask = (y_prob_mask_np >= thr).astype(int)

    # Binary view: mask=1, no_mask=0
    true_mask = (y_true_np == CLASS_TO_IDX['mask']).astype(int)
    p, r, f1, _ = precision_recall_fscore_support(true_mask, pred_mask, average='binary', zero_division=0)
    rows.append((float(thr), float(p), float(r), float(f1)))

    if f1 > best_mask_f1:
        best_mask_f1 = f1
        best_thr = float(thr)

print(f'Best mask threshold={best_thr:.2f} with F1={best_mask_f1:.4f}')
rows[:5], rows[-5:]
```

---

## Cell 10 - Export ONNX

```python
import torch

onnx_path = OUTPUT_ROOT / 'mask_detection.onnx'
model.eval().cpu()

dummy = torch.randn(1, 3, IMG_SIZE, IMG_SIZE)
torch.onnx.export(
    model,
    dummy,
    onnx_path,
    input_names=['input'],
    output_names=['logits'],
    dynamic_axes={'input': {0: 'batch'}, 'logits': {0: 'batch'}},
    opset_version=13,
)

print('Exported ONNX:', onnx_path)
```

---

## Cell 11 - ONNX runtime sanity test

```python
import onnxruntime as ort

session = ort.InferenceSession(str(onnx_path), providers=['CPUExecutionProvider'])
input_name = session.get_inputs()[0].name

# One batch from test set
xb, yb = next(iter(test_loader))
xb_np = xb[:8].numpy()

onnx_logits = session.run(None, {input_name: xb_np})[0]
onnx_preds = np.argmax(onnx_logits, axis=1)

print('ONNX output shape:', onnx_logits.shape)
print('Sample preds:', onnx_preds[:8])
print('Sample true :', yb[:8].numpy())
```

---

## Cell 12 - Save labels, thresholds, metrics

```python
import json
from datetime import datetime
from sklearn.metrics import accuracy_score, f1_score

metrics_payload = {
    'timestamp': datetime.utcnow().isoformat() + 'Z',
    'img_size': IMG_SIZE,
    'labels': LABELS,
    'best_val_f1_macro': float(best_val_f1),
    'test_accuracy': float(accuracy_score(y_true, y_pred)),
    'test_f1_macro': float(f1_score(y_true, y_pred, average='macro')),
    'chosen_mask_threshold': float(best_thr),
}

(OUTPUT_ROOT / 'mask_labels.json').write_text(
    json.dumps({'labels': LABELS, 'class_to_idx': CLASS_TO_IDX}, indent=2),
    encoding='utf-8'
)

(OUTPUT_ROOT / 'mask_thresholds.json').write_text(
    json.dumps({'mask_probability_threshold': float(best_thr)}, indent=2),
    encoding='utf-8'
)

(OUTPUT_ROOT / 'training_metrics.json').write_text(
    json.dumps(metrics_payload, indent=2),
    encoding='utf-8'
)

print('Saved:')
print('-', OUTPUT_ROOT / 'mask_labels.json')
print('-', OUTPUT_ROOT / 'mask_thresholds.json')
print('-', OUTPUT_ROOT / 'training_metrics.json')
print('-', OUTPUT_ROOT / 'mask_detection.onnx')
```

---

## Cell 13 - Optional zip for easy download

```python
import shutil

zip_base = str(ROOT / 'mask_model_bundle')
shutil.make_archive(zip_base, 'zip', OUTPUT_ROOT)
print('Created:', zip_base + '.zip')
```

---

## Integration notes for your backend

After training:

1. Copy artifacts into your project, e.g. `backend/storage/models/face_mask/`.
2. Add config keys for mask model path/threshold.
3. Add `MaskDetectionService` and fuse with face recognition decisions.
4. Apply your selected policy:
   - `authorized + masked -> MASKED_AUTHORIZED_REVIEW`

## Practical data tips for your thesis camera

- Include many low-light / IR-night frames from your `cam_door` stream.
- Include partial-mask, hand-over-mouth, scarf, and side-angle negatives.
- Keep test set strictly separate from people/scenes used in training.
- Prioritize `mask` recall when selecting threshold, then control false alarms.
