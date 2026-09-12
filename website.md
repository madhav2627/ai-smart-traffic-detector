IMPORTANT: Do not start coding immediately. First inspect the supplied ZIP, understand the existing vehicle detection architecture and outputs, and then plan the website integration before making changes.

Do not replace my existing working detection software with mock/demo logic. Build the website around it and keep the detector as the source of truth.

You are working on my AI Intelligent Traffic Surveillance project.

I am providing you an existing vehicle-detection software project:
traffic_ai_complete_improved_FIXED.zip

IMPORTANT:
THIS ZIP CONTAINS MY EXISTING VEHICLE DETECTION SOFTWARE.
DO NOT REBUILD, REPLACE, OR SIMPLIFY THE VEHICLE DETECTION ENGINE.
DO NOT CREATE A FAKE DETECTION SYSTEM.
DO NOT USE PLACEHOLDER DETECTION RESULTS WHEN THE REAL DETECTOR CAN BE USED.

Your job is to build a premium, simple, modern web application around this existing vehicle-detection software.

PROJECT NAME:
SURVILLENCE TRAFFIC
(or use "Surveillance Traffic" wherever grammatically appropriate, while keeping the product branding consistent)

==================================================
1. CORE REQUIREMENT
==================================================

I already have the vehicle detection software.

The website must integrate with that existing software locally.

The application must NOT depend on external APIs.

DO NOT create:
- REST APIs
- third-party APIs
- cloud APIs
- Firebase
- Supabase
- OpenAI APIs
- external authentication APIs
- external traffic APIs
- external AI APIs
- external database APIs

The website and detection system should work as a self-contained local application.

Use:
- HTML
- CSS
- JavaScript
- Tailwind CSS
- Bootstrap
- local/static assets
- local browser functionality
- the existing Python vehicle detection software where required

You may use small additional libraries only when they provide real value and can run locally without requiring an external API.

Do NOT mix Tailwind and Bootstrap unnecessarily.
Use Tailwind for the main modern layout/design system and Bootstrap components/utilities only where useful.
The final interface must look like one unified design, not like two frameworks randomly combined.

==================================================
2. FIRST STEP: ANALYZE MY EXISTING SOFTWARE
==================================================

Before changing anything:

1. Extract and inspect the provided ZIP.
2. Understand the current project structure.
3. Identify:
   - main vehicle detection file
   - YOLO model
   - ByteTrack tracking
   - supported vehicle classes
   - video processing
   - generated processed video
   - JSON/report output
   - configuration files
   - storage directories
   - existing scripts
4. Understand exactly how the detector currently receives:
   - video input
   - image input if supported
   - webcam/CCTV input if supported
5. Understand exactly how it produces:
   - detected vehicles
   - unique vehicle counts
   - active vehicles
   - vehicle classes
   - tracking IDs
   - speed/direction information
   - processed video
   - reports/JSON
6. Preserve the working detection pipeline.

Do not modify the detection algorithm unless absolutely necessary for integration.

==================================================
3. WEBSITE STRUCTURE
==================================================

Create a complete web application with the following flow:

LANDING PAGE
↓
LOGIN
↓
if user does not have account
REGISTRATION
↓
LOGIN
↓
MAIN DASHBOARD

The application should feel like a real commercial AI surveillance platform.

==================================================
4. LANDING PAGE
==================================================

Create a premium, minimal landing page.

Style:
- dark modern theme
- professional surveillance/AI aesthetic
- clean typography
- subtle animations
- not flashy
- not overloaded
- lots of breathing room
- premium SaaS feel

Hero section:

SURVILLENCE TRAFFIC

AI-Powered Traffic Surveillance & Vehicle Analysis

Description:
Monitor traffic, detect vehicles, analyze traffic flow, and generate intelligent insights from surveillance footage using our local AI vehicle detection engine.

Buttons:
- Get Started
- Login

Include sections for:

1. Intelligent Vehicle Detection
2. Real-Time Surveillance
3. Traffic Analytics
4. Vehicle Classification
5. AI-Based Insights
6. Reports & History

Include a visual preview/mock dashboard in the landing page.

The visual should communicate:
- cars
- motorcycles
- autos
- buses
- trucks
- traffic statistics
- surveillance video

Do not use fake claims such as "99.9% accuracy".

==================================================
5. LOGIN PAGE
==================================================

Create a dedicated login page.

Fields:
- Email / Username
- Password

Actions:
- Login
- Remember me
- Forgot password
- Create account

Since this must work without external APIs, implement authentication locally.

Use localStorage or another appropriate local mechanism.

Store only the minimum required information.

Do not store passwords in plain text if a local hashing approach can reasonably be implemented.

If a full backend authentication system is necessary for local operation, build it locally inside the project without relying on external services.

==================================================
6. REGISTRATION PAGE
==================================================

Create registration page.

Fields:
- Full Name
- Email
- Username
- Password
- Confirm Password

Validation:
- required fields
- valid email
- password confirmation
- reasonable password strength
- duplicate local account prevention

After successful registration:
→ redirect to Login

Add:
Already have an account? Login

==================================================
7. AUTHENTICATION FLOW
==================================================

The app must protect the dashboard.

If the user is not authenticated:
→ do not show dashboard pages.

After login:
→ redirect to Dashboard.

Add logout functionality.

Logout must clear the active session.

Prevent directly opening dashboard pages without login.

==================================================
8. MAIN DASHBOARD
==================================================

After login, create the primary surveillance dashboard.

Overall layout:

LEFT SIDEBAR
TOP NAVIGATION
MAIN CONTENT

Sidebar:

Dashboard
Surveillance
Live Monitoring
Vehicle Analytics
Traffic AI
History
Reports
Settings

At bottom:
User profile
Logout

Top navigation:
- search
- notifications
- current system status
- profile

==================================================
9. DASHBOARD HOME
==================================================

Show a clean overview.

Cards:

TOTAL VEHICLES
ACTIVE VEHICLES
CARS
MOTORCYCLES
AUTOS
BUSES
TRUCKS

These values must come from the REAL vehicle detection software.

DO NOT hardcode values such as:
47
17
6
36
or any other manually chosen values.

The website must display actual results generated by the detector.

Dashboard sections:

A. Traffic Overview
- vehicle count chart
- vehicle category chart
- traffic trend
- active vehicles

B. Recent Analysis
Show recently processed videos.

C. Vehicle Distribution
- car
- motorcycle
- auto
- bus
- truck

D. System Status
- AI Engine
- Tracking
- Video Processor
- Storage

Use clear status indicators.

==================================================
10. SURVEILLANCE PAGE
==================================================

Create a dedicated surveillance page.

This is one of the most important pages.

Layout:

LEFT/MAIN:
large surveillance video player

RIGHT:
Live statistics panel

Video controls:
- Play
- Pause
- Mute
- Fullscreen
- playback speed

Above video:
- Camera/source name
- status
- processing state

Statistics:
- Active Vehicles
- Total Vehicles
- Cars
- Motorcycles
- Autos
- Buses
- Trucks

The processed video generated by the existing vehicle detection software should be playable directly in the website.

No external video streaming API.

==================================================
11. VIDEO INPUT
==================================================

Create a page or section for processing traffic videos.

Allow the user to:

- select video from computer
- upload/select local file
- start analysis
- stop analysis
- view processing progress
- open processed result

The selected video must be passed to the existing vehicle detection software.

DO NOT create a second detector.

Use the existing model and tracking pipeline.

==================================================
12. IMPORTANT DETECTION INTEGRATION
==================================================

Integrate the website with the existing detection project.

The current detection system should remain the source of truth.

The website should consume the detector's locally generated output.

Possible local integration approaches:

- local process execution
- local Python execution
- local filesystem communication
- generated JSON files
- generated processed video
- local WebSocket if genuinely necessary
- local server only when required for browser-to-Python communication

Do not use cloud APIs.

Do not create unnecessary network architecture.

If a local backend wrapper is required to connect browser JavaScript with Python, keep it minimal and local.

==================================================
13. DETECTION RESULT FORMAT
==================================================

Create/standardize a local result format if needed.

Example:

{
  "status": "completed",
  "video": "...",
  "total_vehicles": 115,
  "active_vehicles": 36,
  "vehicles": {
    "car": 73,
    "motorcycle": 21,
    "auto": 14,
    "bus": 3,
    "truck": 4
  },
  "average_speed": null,
  "direction": {
    "up": null,
    "down": null,
    "unknown": 100
  }
}

IMPORTANT:
Do NOT fabricate missing information.

If speed cannot be reliably determined:
show:
N/A

If direction cannot be reliably determined:
show:
Unknown

Do not insert fake fallback values.

==================================================
14. NO COUNTING LINE
==================================================

This is extremely important.

There must be NO red counting line.

There must be NO:
- line crossing detection
- virtual counting line
- COUNT_LINE
- LINE_Y
- counting boundary
- "vehicle crossed the line" logic

The system should count vehicles based on tracked vehicle identities.

The UI must also NOT show a red counting line over the video.

The website should simply show detection/tracking bounding boxes and labels when available.

==================================================
15. VEHICLE CATEGORIES
==================================================

Use the existing detector's normalized vehicle classes.

Main UI categories:

Car
Motorcycle
Auto
Bus
Truck

If the detector identifies detailed source classes such as:

Hatchback
Sedan
SUV
MUV
Van

they may be grouped under:

CAR

Two-wheeler:
MOTORCYCLE

Three-wheeler:
AUTO

Bus:
BUS

Truck / LCV:
TRUCK

Use the actual mapping from the supplied detector project.

==================================================
16. VEHICLE ANALYTICS PAGE
==================================================

Create a premium analytics page.

Show:

Total Vehicles
Active Vehicles
Vehicle Distribution
Traffic Density
Detection Timeline
Average Vehicles / Minute
Peak Traffic Period
Vehicle Type Distribution

Charts should be generated from actual detector data.

Do not create fake statistics simply to make charts look populated.

If data is unavailable, display an appropriate empty state:

"No analysis data available yet."

==================================================
17. TRAFFIC AI PAGE
==================================================

Create a dedicated AI insights page.

Show insights based only on actual available data.

Examples:

Traffic Density
Low / Moderate / High

Dominant Vehicle Type

Peak Traffic Period

Vehicle Flow

Detection Summary

Do not invent AI conclusions when the data is insufficient.

==================================================
18. HISTORY PAGE
==================================================

Show previously processed videos.

Each history item should contain:

- filename
- date
- duration
- total vehicles
- processing status
- view result
- delete

Store history locally.

==================================================
19. REPORTS PAGE
==================================================

Create a reports page.

Allow users to view analysis summaries.

Show:

- analysis date
- video name
- total vehicles
- vehicle distribution
- active vehicles
- traffic density
- processing duration

Provide:

View Report
Download Report

Reports must be generated locally.

No external reporting API.

==================================================
20. SETTINGS PAGE
==================================================

Include:

Profile
Appearance
Notifications
Detection Settings
Storage
System Information

Appearance:
- Dark
- Light

Default should be premium dark mode.

Detection settings should expose only safe configuration options.
Do not expose dangerous technical settings unnecessarily.

==================================================
21. DESIGN SYSTEM
==================================================

Use a premium dark visual language.

Preferred characteristics:

- very dark background
- slightly lighter cards
- subtle borders
- rounded corners
- clean typography
- restrained accent color
- subtle gradients
- small glowing status indicators
- smooth hover transitions
- modern icons
- clean charts

Avoid:
- excessive neon
- excessive glassmorphism
- huge text everywhere
- excessive animations
- cluttered cards
- childish dashboard appearance

The design should feel like a professional AI command center.

==================================================
22. RESPONSIVE DESIGN
==================================================

The website must work on:

Desktop
Laptop
Tablet
Mobile

Sidebar should collapse appropriately.

Video panel should resize correctly.

Tables and charts should remain usable on smaller screens.

==================================================
23. UI COMPONENTS
==================================================

Create reusable components for:

Sidebar
Topbar
StatCard
VideoPlayer
VehicleBadge
StatusBadge
ChartCard
UploadCard
HistoryCard
Modal
Toast
Dropdown
EmptyState
LoadingState
ErrorState

Maintain consistent spacing and typography.

==================================================
24. LOADING / ERROR STATES
==================================================

Every important action needs feedback.

Examples:

Processing video...

Detection engine starting...

Analyzing frames...

Generating report...

Analysis completed.

Analysis failed.

AI engine unavailable.

No video selected.

No analysis data available.

Do not leave the interface appearing frozen.

==================================================
25. FILE MANAGEMENT
==================================================

Keep the project organized.

Suggested structure:

/frontend
  /pages
  /components
  /assets
  /css
  /js

/backend
  existing detector integration

/models
  existing required models

/storage
  videos
  results
  reports
  history

Do not duplicate the model.

Do not duplicate the detection software.

Do not copy huge model files unnecessarily.

==================================================
26. PERFORMANCE
==================================================

Optimize the website.

Do not load huge assets unnecessarily.

Do not repeatedly process the same video.

Do not reload the detector unnecessarily.

Cache appropriate results locally.

Clean temporary files after processing when safe.

Use efficient video playback.

Use lazy loading where appropriate.

==================================================
27. IMPORTANT: PRESERVE THE AI ENGINE
==================================================

The following existing functionality must remain working:

- YOLO vehicle detection
- UVH-26 model
- ByteTrack tracking
- vehicle class normalization
- unique vehicle identification
- processed video generation
- JSON/report generation

Do not replace the existing model with a different model.

Do not downgrade the detection system.

Do not add a second model.

==================================================
28. REMOVE OLD/UNUSED CODE CAREFULLY
==================================================

As part of integration:

Find obsolete files and duplicated code.

Remove only code/files proven unnecessary.

Do not delete:
- vehicle_traffic.pt
- required Python source
- required configuration
- required assets
- dependencies
- storage required by the application

Do remove:
- obsolete line-count logic if it still exists anywhere
- debugging artifacts
- temporary generated files
- fake hardcoded statistics
- duplicate model copies
- unused sample output
- unnecessary caches

==================================================
29. CODE QUALITY
==================================================

Write clean maintainable code.

Use:
- semantic HTML
- modular JavaScript
- reusable CSS
- reusable UI components
- meaningful variable names
- comments only where useful

Avoid giant single files when functionality can be separated cleanly.

==================================================
30. BEFORE IMPLEMENTATION
==================================================

First inspect the supplied ZIP completely.

Create a short internal architecture summary:

Existing detector:
Existing model:
Tracking:
Input:
Output:
Video output:
JSON output:
Storage:
Required Python dependencies:

Then build the frontend around it.

==================================================
31. FINAL TESTING
==================================================

Before declaring the project complete:

Test:

1. Open landing page.
2. Registration works.
3. Login works.
4. Unauthorized users cannot access dashboard.
5. Logout works.
6. Dashboard loads.
7. Video selection works.
8. Existing detector starts correctly.
9. Real vehicle detections appear.
10. No red counting line appears.
11. Vehicle totals come from real detector results.
12. Active vehicle count comes from actual current result.
13. No hardcoded vehicle counts remain.
14. No fake speed fallback remains.
15. No fabricated direction percentages remain.
16. Processed video plays in browser.
17. History is saved.
18. Reports work.
19. Settings work.
20. Mobile layout works.
21. Refresh does not corrupt the session.
22. Missing data displays N/A or an empty state instead of fake values.

==================================================
32. FINAL DELIVERABLE
==================================================

Give me:

1. Complete working website.
2. Existing vehicle detection software integrated with it.
3. Clean project structure.
4. No external APIs.
5. No fake analytics.
6. No counting line.
7. Real vehicle detection results.
8. Premium landing page.
9. Login.
10. Registration.
11. Dashboard.
12. Surveillance.
13. Vehicle Analytics.
14. Traffic AI.
15. History.
16. Reports.
17. Settings.

MOST IMPORTANT:

This is not a mockup.

I want a FUNCTIONAL local AI traffic surveillance application built around the vehicle detection software I provided.

The existing vehicle detector is the foundation of the product.

Do not replace it with mock data or another detection system.
==================================================
33. FINAL INTEGRATION CONTRACT — VERY IMPORTANT
==================================================

Treat the supplied traffic_ai_complete_improved_FIXED.zip as the SOURCE OF TRUTH for vehicle detection.

Do not invent a new detection workflow.

Before changing integration code, inspect the existing detector and document exactly:

- the command needed to start detection
- the Python entry point
- required arguments
- model path
- tracker configuration
- input video location
- output video location
- JSON/report output location
- processing status
- error behavior

Then connect the website to that exact workflow.

The website must be able to:

1. Select a local traffic video.
2. Send that video to the existing detector through the LOCAL integration mechanism.
3. Start real processing.
4. Show processing progress.
5. Read the real generated results.
6. Display the real processed video.
7. Display real vehicle counts.
8. Display real vehicle categories.
9. Display real active vehicle information when available.
10. Display real speed/direction only when the detector has valid data.
11. Save the completed analysis to local history.
12. Re-open a previous analysis without running detection again.

==================================================
34. ONE SOURCE OF TRUTH FOR RESULTS
==================================================

Never calculate a second set of vehicle counts in JavaScript.

The detector is the authoritative source.

The frontend must display the detector's output.

Do NOT do this:

Detector says 73 cars
Frontend independently counts bounding boxes
Frontend displays 81 cars

Instead:

Detector → result file → frontend → display

==================================================
35. REAL-TIME VS PROCESSED VIDEO
==================================================

Clearly distinguish between:

LIVE / INPUT VIDEO
and
PROCESSED / ANALYZED VIDEO

Do not label a pre-recorded processed video as "LIVE".

If there is no true live camera source, use labels such as:

VIDEO ANALYSIS
PROCESSED VIDEO
RECORDED SURVEILLANCE

Do not fake real-time functionality.

==================================================
36. CCTV / CAMERA ARCHITECTURE
==================================================

Design the UI so CCTV/camera support can be added later.

For now, support the existing local video-processing workflow completely.

Create the UI structure for:

Camera 01
Camera 02
Camera 03
etc.

But DO NOT invent a working CCTV stream if the supplied software does not currently support one.

Show appropriate states such as:

ONLINE
OFFLINE
NO SIGNAL
NOT CONFIGURED

when applicable.

==================================================
37. DATA PERSISTENCE
==================================================

Use local persistence for:

- registered users
- current session
- analysis history
- saved reports
- application settings

Do not require a cloud database.

Do not require an external authentication service.

Use a local database/file-based mechanism when appropriate.

Keep the data structure simple and maintainable.

==================================================
38. SECURITY
==================================================

Even though this is a local application:

- validate all user inputs
- validate uploaded file types
- prevent path traversal
- sanitize filenames
- do not expose arbitrary filesystem access to the browser
- do not allow the browser to execute arbitrary commands
- restrict local process execution to the known detector command
- do not expose secrets in frontend JavaScript
- do not commit passwords or secrets into source code

==================================================
39. FILE CLEANUP AFTER INTEGRATION
==================================================

After successful integration, identify temporary/generated files that are safe to remove.

Do not keep unnecessary copies of:

- uploaded videos
- intermediate frames
- temporary encoded files
- debug images
- cache files
- duplicate reports

However, retain files required for:

- history
- reports
- processed video playback
- reproducibility

Provide a clear storage-management mechanism in Settings.

==================================================
40. DEMO MODE — ONLY WHEN EXPLICITLY LABELED
==================================================

For UI development, you may temporarily use sample/demo data.

BUT:

- clearly label it as DEMO
- keep demo data isolated
- never mix demo data with real detector results
- never allow demo data to appear as real analysis

Once integration is complete, make the REAL detector the default.

==================================================
41. COMPLETE END-TO-END TEST
==================================================

Perform one complete test using an actual traffic video from the supplied project or an appropriate test video.

Test this exact flow:

Landing Page
→ Registration
→ Login
→ Dashboard
→ Upload Video
→ Start Analysis
→ Existing YOLO + ByteTrack Detector
→ Process Video
→ Generate Results
→ Display Processed Video
→ Display Real Vehicle Counts
→ Display Analytics
→ Save History
→ Open Report
→ Logout

During this test verify:

- no counting line
- no hardcoded counts
- no fake analytics
- no duplicate counting caused by the frontend
- no incorrect category mapping
- no broken video playback
- no missing result files
- no stale results from a previous video
- no accidental mixing of two analyses

==================================================
42. FINAL CODE AUDIT
==================================================

Before completion, search the entire project for suspicious hardcoded analytics such as:

- 47
- 17
- 6
- 2
- 1
- 36
- 66.4
- 72%
- 28%

Do NOT blindly delete these numbers if they are legitimate UI dimensions or unrelated values.

Check their context.

Remove any remaining hardcoded traffic-analysis values that were previously being used as fake detector results.

Also search for and remove obsolete logic related to:

- COUNT_LINE
- LINE_Y
- line crossing
- virtual counting line
- crossing direction
- red counting boundary

unless such code is genuinely required by another unrelated feature.

==================================================
43. FINAL ACCEPTANCE CRITERIA
==================================================

The project is complete ONLY when all of the following are true:

[ ] Premium landing page
[ ] Login
[ ] Registration
[ ] Local authentication
[ ] Protected dashboard
[ ] Surveillance page
[ ] Video upload
[ ] Existing detector integration
[ ] Real YOLO detection
[ ] ByteTrack tracking
[ ] Real unique vehicle counting
[ ] No counting line
[ ] No fake counts
[ ] No fake speed
[ ] No fake direction statistics
[ ] Real processed video
[ ] Real analytics
[ ] History
[ ] Reports
[ ] Settings
[ ] Local persistence
[ ] Responsive design
[ ] Error handling
[ ] Loading states
[ ] Empty states
[ ] Storage cleanup
[ ] No external APIs
[ ] No cloud dependency
[ ] No duplicate detector implementation
[ ] No unnecessary model copies
[ ] Successful end-to-end test

==================================================
44. DO NOT STOP AT THE UI
==================================================

A visually complete website is NOT considered complete.

The final application must actually work from:

UPLOAD VIDEO
→ DETECT
→ TRACK
→ COUNT
→ GENERATE RESULT
→ DISPLAY RESULT

using the supplied vehicle detection software.

If any part of that chain is not working, continue debugging and fixing it before declaring the project complete.

==================================================
45. FINAL RESPONSE FROM YOU
==================================================

After implementation, provide a concise technical summary containing:

Architecture:
Frontend:
Local integration:
Detector:
Model:
Tracker:
Data storage:
Authentication:
Video handling:

Also provide:

- files created
- files modified
- files removed
- how to start the application
- how to start the detector
- how the frontend communicates with the detector locally
- where processed videos are stored
- where reports are stored
- where history is stored
- any remaining limitations

Do not claim a feature works unless you actually tested it.
==================================================
46. USE LOVABLE + MOBBIN FOR DESIGN RESEARCH
==================================================

You have access to LOVABLE and MOBBIN through connected MCPs.

USE THEM actively during the design and implementation process.

Do NOT simply mention them in the final response.
Actually use them to improve the website design.

MOBBIN:
Use Mobbin to research high-quality modern SaaS, AI dashboard, analytics, surveillance, monitoring, authentication, navigation, cards, charts, tables, settings, and landing-page patterns.

Look for inspiration for:

- premium AI SaaS landing pages
- dark-mode dashboards
- surveillance/command-center interfaces
- login pages
- registration pages
- sidebar navigation
- analytics dashboards
- data visualization
- video monitoring interfaces
- status indicators
- history tables
- reports
- settings pages
- responsive mobile navigation

Use Mobbin as DESIGN INSPIRATION ONLY.

Do not copy another company's branding, logo, exact visual identity, proprietary illustrations, or copyrighted assets.

Instead:
- study layout patterns
- study spacing
- study typography hierarchy
- study navigation patterns
- study card composition
- study information density
- study responsive behavior
- study interactions
- study visual hierarchy

Then create an original design for SURVILLENCE TRAFFIC.

--------------------------------------------------

LOVABLE:
Use Lovable to explore strong implementation patterns and modern UI approaches for:

- dashboard layouts
- reusable components
- authentication screens
- analytics pages
- responsive layouts
- dark themes
- charts
- tables
- upload interfaces
- video interfaces
- empty/loading/error states
- settings
- navigation

Use Lovable as a reference for implementation quality and component structure.

Do NOT blindly copy generated code.

Adapt the useful ideas to the existing project architecture.

--------------------------------------------------

DESIGN PROCESS:

Before implementing the UI:

1. Inspect the existing project.
2. Use Mobbin to research relevant design patterns.
3. Use Lovable to research/validate modern UI implementation approaches.
4. Select the strongest patterns.
5. Create a cohesive design system for SURVILLENCE TRAFFIC.
6. Then implement the design.

Do not create disconnected pages that look like different templates.

Every page must belong to the same product.

--------------------------------------------------

DESIGN DIRECTION:

The final design should feel like:

Premium AI Traffic Intelligence Platform
+
Professional Surveillance Command Center
+
Modern SaaS Analytics Product

Visual qualities:

- premium
- minimal
- sophisticated
- highly readable
- dark-first
- spacious
- clean
- professional
- technically advanced
- trustworthy

Avoid:

- generic AI landing-page templates
- excessive gradients
- excessive glassmorphism
- excessive glowing elements
- giant meaningless headings
- too many cards
- clutter
- unnecessary animations
- childish colors
- template-looking UI

--------------------------------------------------

DESIGN SYSTEM:

Create a unified design system before building all pages.

Define:

- primary background
- secondary background
- card background
- border treatment
- typography scale
- heading hierarchy
- body text
- muted text
- accent color
- success state
- warning state
- error state
- status indicators
- border radius
- shadows
- spacing scale
- button styles
- input styles
- table styles
- chart styles

Keep the visual language consistent throughout the application.

--------------------------------------------------

LANDING PAGE DESIGN:

Use Mobbin/Lovable research to make the landing page feel like a premium technology company.

Suggested structure:

Hero
→ Product visualization
→ Core capabilities
→ How it works
→ Vehicle intelligence
→ Analytics preview
→ Surveillance preview
→ Reports
→ CTA
→ Footer

Do not make it excessively long.

The product should be understandable within a few seconds.

--------------------------------------------------

DASHBOARD DESIGN:

Use the research to create a highly usable command-center dashboard.

Prioritize:

1. Current traffic state
2. Active vehicles
3. Vehicle distribution
4. Surveillance video
5. Traffic trends
6. Recent analyses

Do not fill the screen with unnecessary widgets.

Information hierarchy is more important than the number of components.

--------------------------------------------------

SURVEILLANCE DESIGN:

Make the video the visual focus.

Use a professional monitoring layout.

Example structure:

------------------------------------------------
| Camera / Analysis Status                    |
------------------------------------------------
|                                              |
|               VIDEO                          |
|                                              |
|                                              |
------------------------------------------------
| Active | Cars | Bikes | Autos | Bus | Truck |
------------------------------------------------

Then provide detailed analysis below.

Do NOT add a red counting line.

--------------------------------------------------

RESPONSIVE DESIGN:

Use the Mobbin research particularly for mobile behavior.

Do not simply shrink the desktop interface.

Design mobile states intentionally.

Desktop:
Sidebar + content

Tablet:
Collapsed/sidebar drawer

Mobile:
Bottom navigation or compact menu where appropriate

Ensure video, charts and tables remain usable.

--------------------------------------------------

FINAL DESIGN REVIEW:

After implementation, perform a visual review of every page.

Check:

Landing
Login
Registration
Dashboard
Surveillance
Live Monitoring
Vehicle Analytics
Traffic AI
History
Reports
Settings

Check for:

- inconsistent spacing
- inconsistent typography
- inconsistent border radius
- poor alignment
- excessive empty space
- excessive information density
- weak contrast
- confusing navigation
- poor mobile layout
- unnecessary components
- visual inconsistencies

Fix these before declaring the project complete.

The final result should look like a professionally designed product, not a collection of AI-generated templates.

--------------------------------------------------

MOST IMPORTANT:

Use LOVABLE + MOBBIN as active design resources during the build.

Do not skip this step.

Do not merely mention that they were available.

Use the insights from them to make SURVILLENCE TRAFFIC significantly better designed while keeping the final implementation original.