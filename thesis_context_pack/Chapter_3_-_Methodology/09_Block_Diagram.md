# Block Diagram

Figure 7. Block Diagram

The block diagram below presents the integrated architecture of the prototype. The system monitors two areas: **Living Room** and **Door Entrance Area**. It combines camera inputs, smoke-sensing nodes, a door-force node, local monitoring services, and optional remote access layers. Raspberry Pi 2 is represented as an optional deployment component for local edge hosting.

```text
+-------------------+      +-------------------+
| Camera Input A    |      | Camera Input B    |
| Living Room       |      | Door Entrance     |
+-------------------+      +-------------------+
          |                           |
          +-------------+-------------+
                        |
                        v
              +-----------------------+
              | Detection Modules     |
              | - Face Recognition    |
              | - Fire Confirmation   |
              +-----------------------+
                        |
                        v
+-------------------+   +-----------------------+   +-------------------+
| Smoke Node 1      |-->| Event / Fusion Engine |<--| Smoke Node 2      |
| Living Room       |   | - Intruder Logic      |   | Door Entrance     |
+-------------------+   | - Fire Logic          |   +-------------------+
                        | - Alert Decisions     |
+-------------------+   +-----------------------+
| Door-Force Node   |--------------->|
| Door Entrance     |                v
+-------------------+      +---------------------------+
                           | Local Monitoring Services |
                           | - Alerts / ACK            |
                           | - Logs / Snapshots        |
                           | - Daily Summaries         |
                           | - Dashboard               |
                           +---------------------------+
                                        |
                                        v
                           +---------------------------+
                           | Optional Remote Layers    |
                           | Mobile / Telegram / LAN   |
                           +---------------------------+

                           +---------------------------+
                           | Raspberry Pi 2            |
                           | Optional Local Edge Host  |
                           +---------------------------+
```
