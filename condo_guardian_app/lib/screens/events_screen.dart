import 'package:flutter/material.dart';

import '../models/alert_item.dart';
import '../services/backend_service.dart';

class EventsScreen extends StatefulWidget {
  const EventsScreen({
    super.key,
    required this.backendService,
    this.initialDate,
  });

  final BackendService backendService;
  final DateTime? initialDate;

  @override
  State<EventsScreen> createState() => _EventsScreenState();
}

class _EventsScreenState extends State<EventsScreen> {
  bool _loading = true;
  String? _error;
  List<AlertItem> _events = <AlertItem>[];
  DateTime? _selectedDate;

  @override
  void initState() {
    super.initState();
    if (widget.initialDate != null) {
      _selectedDate = DateTime(
        widget.initialDate!.year,
        widget.initialDate!.month,
        widget.initialDate!.day,
      );
    }
    _loadEvents();
  }

  Future<void> _loadEvents() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final events =
          await widget.backendService.fetchEvents(localDate: _selectedDate);
      if (!mounted) {
        return;
      }
      setState(() {
        _events = events;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _error = '$error';
      });
    }
  }

  Color _severityColor(String severity) {
    switch (severity.toLowerCase()) {
      case 'critical':
        return Colors.red;
      case 'warning':
        return Colors.orange;
      default:
        return Colors.blue;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Events')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Text(
                          'Could not load events.',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        Text(_error!),
                        const SizedBox(height: 12),
                        FilledButton(
                          onPressed: _loadEvents,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _events.isEmpty
                  ? const Center(child: Text('No events at the moment.'))
                  : RefreshIndicator(
                      onRefresh: _loadEvents,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _events.length,
                        itemBuilder: (context, index) {
                          final event = _events[index];
                          return Card(
                            child: ListTile(
                              leading: CircleAvatar(
                                backgroundColor: _severityColor(event.severity),
                              ),
                              title: Text(event.title),
                              subtitle:
                                  Text('${event.message}\n${event.createdAt}'),
                              isThreeLine: true,
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
