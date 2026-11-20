# Coding checklist by member

## M1 – Lý Trường Đạt (SUB-01 + integration)
- [x] Create app entry point and module structure
- [x] Seed shared demo data and canonical enums
- [x] Implement Hub listing/details and vehicle filtering
- [x] Implement create/cancel/expire/consume reservation foundation
- [ ] Review common data contracts with M2–M6
- [ ] Integrate members' modules and verify full demo flows

## M2 – Nguyễn Thị Anh Thư (Authentication + SUB-02)
- [ ] Replace temporary role selector with Sign Up / Sign In / Sign Out screens
- [ ] Implement UC-04 pickup and reservation validation
- [ ] Call SUB-01 consume function after successful pickup
- [ ] Implement UC-05 return and battery/status update
- [ ] Provide low-battery charging request to SUB-04

## M3 – Trần Yến Linh (SUB-03)
- [ ] Implement UC-06-01 parking reservation and temporary hold
- [ ] Implement UC-06-02 cancellation
- [ ] Implement UC-06-03 check-in/check-out with simulated sensor buttons
- [ ] Implement UC-07-01 charging request
- [ ] Implement UC-07-02 cancellation coordinated with SUB-04

## M4 – Lương Chí Thịnh (SUB-04)
- [ ] Implement UC-08 charging resource monitoring
- [ ] Implement UC-09 request priority and missing-data handling
- [ ] Implement UC-10 schedule proposal, validation and confirmation
- [ ] Expose functions for SUB-02/SUB-03 request and cancellation

## M5 – Hồ Nguyễn Thùy Dung (SUB-05)
- [ ] Implement UC-11 network dashboard
- [ ] Implement UC-12 Near Capacity detection
- [ ] Implement UC-13 redistribution with eligibility/capacity checks
- [ ] Implement UC-14 incident create/update/resolve

## M6 – Dương Minh Huy (SUB-06)
- [ ] Implement UC-15 scenario selection and parameters
- [ ] Implement UC-16 simulation on copied snapshot
- [ ] Implement UC-17 impact evaluation and recommendations
- [ ] Verify simulation leaves operational state unchanged
