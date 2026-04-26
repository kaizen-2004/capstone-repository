import 'package:flutter/material.dart';

import '../services/backend_service.dart';

class AssistantScreen extends StatefulWidget {
  const AssistantScreen({super.key, required this.backendService});

  final BackendService backendService;

  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends State<AssistantScreen> {
  static const _questions = <String, ({String label, IconData icon})>{
    'current_system_status': (
      label: 'What is the current system status?',
      icon: Icons.shield_outlined,
    ),
    'last_alert_reason': (
      label: 'What triggered the last alert?',
      icon: Icons.warning_amber_outlined,
    ),
    'which_node_detected_smoke': (
      label: 'Which node detected smoke?',
      icon: Icons.sensors_outlined,
    ),
    'are_any_nodes_offline': (
      label: 'Are any nodes offline?',
      icon: Icons.hub_outlined,
    ),
    'recent_intrusion_events': (
      label: 'What recent intrusion events were logged?',
      icon: Icons.door_front_door_outlined,
    ),
    'explain_current_warning': (
      label: 'Explain the current warning.',
      icon: Icons.help_outline_rounded,
    ),
  };

  String? _selectedId;
  bool _loading = false;
  String _answer = '';

  Future<void> _submit(String id) async {
    setState(() {
      _selectedId = id;
      _loading = true;
    });
    try {
      final answer = await widget.backendService.queryAssistant(id);
      if (mounted) {
        setState(() {
          _answer = answer;
          _loading = false;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _answer = '$error';
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: cs.primary.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: cs.primary.withValues(alpha: 0.2)),
          ),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: cs.primary.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  Icons.smart_toy_rounded,
                  color: cs.primary,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'AI Assistant',
                      style: tt.titleLarge?.copyWith(fontSize: 15),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Select a guided question to get an answer.',
                      style: tt.bodySmall,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        Text(
          'QUESTIONS',
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w700,
            color: cs.onSurfaceVariant,
            letterSpacing: 1.3,
          ),
        ),
        const SizedBox(height: 8),
        ..._questions.entries.map((entry) {
          final isSelected = _selectedId == entry.key;
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: _QuestionButton(
              label: entry.value.label,
              icon: entry.value.icon,
              isSelected: isSelected,
              isLoading: isSelected && _loading,
              disabled: _loading,
              onTap: () => _submit(entry.key),
            ),
          );
        }),
        const SizedBox(height: 20),
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 300),
          child: _selectedId == null
              ? _EmptyAnswer()
              : _loading
                  ? _LoadingAnswer()
                  : _AnswerCard(
                      question: _questions[_selectedId!]!.label,
                      answer: _answer,
                    ),
        ),
      ],
    );
  }
}

class _QuestionButton extends StatelessWidget {
  const _QuestionButton({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.isLoading,
    required this.disabled,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool isSelected;
  final bool isLoading;
  final bool disabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      decoration: BoxDecoration(
        color: isSelected
            ? cs.primary.withValues(alpha: 0.12)
            : cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isSelected
              ? cs.primary.withValues(alpha: 0.5)
              : cs.outlineVariant,
          width: isSelected ? 1.5 : 1,
        ),
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: disabled ? null : onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(
              children: [
                Icon(
                  icon,
                  size: 18,
                  color: isSelected ? cs.primary : cs.onSurfaceVariant,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    label,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          fontSize: 13,
                          color: isSelected
                              ? cs.onSurface
                              : cs.onSurface.withValues(alpha: 0.85),
                          fontWeight:
                              isSelected ? FontWeight.w600 : FontWeight.w400,
                        ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                if (isLoading)
                  SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: cs.primary,
                    ),
                  )
                else
                  Icon(
                    Icons.chevron_right_rounded,
                    size: 18,
                    color: isSelected ? cs.primary : cs.outlineVariant,
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _EmptyAnswer extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Column(
        children: [
          Icon(
            Icons.chat_bubble_outline_rounded,
            size: 32,
            color: cs.onSurfaceVariant.withValues(alpha: 0.4),
          ),
          const SizedBox(height: 10),
          Text(
            'Response will appear here',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: cs.onSurfaceVariant.withValues(alpha: 0.6),
                ),
          ),
        ],
      ),
    );
  }
}

class _LoadingAnswer extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2, color: cs.primary),
          ),
          const SizedBox(width: 12),
          Text(
            'Generating response…',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }
}

class _AnswerCard extends StatelessWidget {
  const _AnswerCard({required this.question, required this.answer});

  final String question;
  final String answer;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    return Container(
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: cs.primary.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: cs.primary.withValues(alpha: 0.08),
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(14)),
              border: Border(
                  bottom:
                      BorderSide(color: cs.primary.withValues(alpha: 0.15))),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.help_outline_rounded, size: 14, color: cs.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    question,
                    style: tt.bodySmall?.copyWith(
                        color: cs.primary, fontWeight: FontWeight.w600),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.smart_toy_rounded,
                  size: 16,
                  color: cs.primary.withValues(alpha: 0.7),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    answer,
                    style: tt.bodyMedium?.copyWith(height: 1.6),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
