# Coding Checklist by Member (Completed Status)

## M1 – Lý Trường Đạt (SUB-01 + Integration)
- [x] Create app entry point, unified UI kit, and module structure
- [x] Seed shared demo data, audit logs, and canonical enums
- [x] Implement Hub listing/details, 2D Hub network map, and vehicle filtering
- [x] Implement create/cancel/expire/consume reservation foundation
- [x] Review common data contracts with M2–M6
- [x] Integrate members' modules and verify full demo flows

## M2 – Nguyễn Thị Anh Thư (Authentication + SUB-02)
- [x] Implement Sign Up / Sign In / Sign Out screens with hashed passwords
- [x] Implement UC-04 pickup, QR/vehicle selection, pickup code validation, and faulty vehicle swap
- [x] Call SUB-01 consume function after successful pickup
- [x] Implement UC-05 return, nearby Hub suggestions when full, inline/mid-trip/post-return fault reporting
- [x] Provide low-battery charging request (`< 20%`) to SUB-04

## M3 – Trần Yến Linh (SUB-03)
- [x] Implement UC-06-01 visual parking grid, 5-minute temporary hold, and parking reservation
- [x] Implement UC-06-02 cancellation with cascading charging cleanup
- [x] Implement UC-06-03 check-in/check-out with active-charging safety guard
- [x] Implement UC-07-01 charging request with reference Hub charger availability
- [x] Implement UC-07-02 cancellation coordinated with SUB-04

## M4 – Lương Chí Thịnh (SUB-04)
- [x] Implement UC-08 charging resource & time-window load monitoring
- [x] Implement UC-09 request priority (`< 30%` battery, departure time, FIFO) and missing/stale data separation
- [x] Implement UC-10 schedule proposal, custom adjustment, confirmation, progress tracking, and faulty-point replacement
- [x] Expose functions for SUB-02/SUB-03 request, completion, and cancellation

## M5 – Hồ Nguyễn Thùy Dung (SUB-05)
- [x] Implement UC-11 network dashboard & Hub detail inspector
- [x] Implement UC-12 Near Capacity (`<= 20%` free) detection with stale/disconnected reliability guard
- [x] Implement UC-13 redistribution with destination space hold & reservation protection
- [x] Implement UC-14 incident create/update/emergency-stop/resolve & System Audit Log

## M6 – Dương Minh Huy (SUB-06)
- [x] Implement UC-15 all 5 What-if scenarios (`Peak Arrivals`, `Full Parking`, `Charging Surge`, `Point Failures`, `Vehicle Concentration`) & parameter validation
- [x] Implement UC-16 simulation on immutable snapshot in isolated sandbox
- [x] Implement UC-17 impact evaluation, operational recommendations, CSV export & module navigation shortcuts
- [x] Verify simulation leaves operational state 100% unchanged
