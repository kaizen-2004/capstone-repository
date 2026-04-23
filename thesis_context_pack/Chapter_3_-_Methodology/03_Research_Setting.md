# Research Setting

The study was conducted in two primary settings:

1. **University Laboratory / Workshop**  
This setting was used for literature review, architecture design, programming, bench-top validation of core modules, and iterative debugging of the integrated monitoring workflow. It was also the setting in which the researchers tested deployment options, including local edge-hosting arrangements in which Raspberry Pi 2 may be incorporated when needed.

2. **Condo-like / Simulated Condominium Environment**  
This setting was used for integrated system deployment and scenario-based testing. The implementation scope covered two monitored areas only:
- **Living Room**
- **Door Entrance Area**

In this setup, one camera input monitored interior activity and fire-related visual cues, while another camera input monitored the entrance area. Two smoke nodes and one door-force node sent event data to the monitoring backend through HTTP POST + JSON using `POST /api/sensors/event`. This setting was used to observe how the full workflow behaved under controlled, repeatable scenarios.
