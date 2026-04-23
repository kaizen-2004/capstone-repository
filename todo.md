- [ ] Assemble Nodes
	- [x] Smoke Sensor Node 1
	- [x] Smoke Sensor Node 2
	- [x] Door Force Sensor Node
	- [ ] Outdoor Camera ESP32-CAM Node
**SOFTWARE:**
- [ ] Make an executable file of the application.
- [ ] Make an interactive instruction manual of the software
- [ ] Test the software
- [ ] Add a configurable backend IP, CAN_INDOOR_RTSP, CAM_DOOR.
- [ ] Add an emergency contacting feature when an intruder is detected it will notify either the condo security, police, or BFP via 911.
- [ ] A Telegram AI chatbot feature will be implemented to allow users to query real-time sensor status, receive automated alerts, and obtain AI-generated explanations of detected events through a conversational interface. The system will integrate the Telegram Bot API with backend sensor monitoring and rule-based alert logic, using an LLM to provide human-readable interpretations of system conditions.
**HARDWARE:**
- [ ] Add a buzzer to the smoke sensor nodes so that it will notify the resident of the condo when a smoke is detected.
- [ ] Instead of using FireNet for flame detection, we will now migrate to MLX906040 Thermal Camera Module. 
- [ ] Assemble the ESP32-CAM — Door Camera Node — and make it RTSP Stream [Source](https://github.com/rzeldent/esp32cam-rtsp).
