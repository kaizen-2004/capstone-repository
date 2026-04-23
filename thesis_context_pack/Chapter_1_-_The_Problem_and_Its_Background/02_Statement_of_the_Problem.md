### **Title**

**Real-Time Intruder and Fire Monitoring Alert System Using IoT Facial Recognition with Night-Vision Camera**

---

### **1. Main Objective**

The main objective of this research is to **design, construct, and evaluate a real-time intruder and fire monitoring alert system** that uses **night-vision-capable cameras for OpenCV-based facial recognition and fire-related visual analysis**, together with **smoke sensors and a door motion/force sensor**, to provide timely and persistent warnings to the user in a condo-like environment.

### **2. Specific Objectives**

Specifically, the study aims to:

1. **Design** the overall **system architecture** that integrates camera inputs, local monitoring software, environmental sensing, and optional local edge-hosting components such as **Raspberry Pi 2** for intruder and fire-related monitoring.
2. **Develop** the core detection algorithms by
   - implementing an **OpenCV-based facial detection and recognition pipeline** for identifying authorized versus unknown individuals, and
   - creating a **visual fire-confirmation algorithm** that analyzes indoor camera footage when smoke-related events occur.
3. **Implement** the integrated system by
   - constructing the necessary **hardware and software interfaces** among the local host environment, the cameras, the smoke sensors, and the door sensor, and
   - enabling **automatic logging and classification** of intruder-related and fire-related events based on multi-sensor fusion.
4. **Generate** a **summary of event and identification statistics** over a given period (e.g., daily), including
   - the number of **recognized authorized faces**,
   - the number of **unrecognized or suspicious detections**,
   - the number of **detected fire-related visual and smoke events**.
5. **Evaluate** the system’s overall **reliability and performance** in terms of
   - **face identification accuracy**,
   - **fire-related detection performance**, including **visual flame and smoke-sensor false-positive and false-negative rates**, and
   - **system response time** from event occurrence to alert activation.

---

### **Keywords**

IoT Monitoring, Facial Recognition, Fire Detection, Smoke Detection, Real-Time Detection, Night-Vision Camera
