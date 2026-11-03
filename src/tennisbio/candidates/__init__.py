"""Candidate models (docs/plan_maestro.md, "Plan a corto plazo (02-11)", paso 2): the models of the reference
project «Claude as a Tennis Coach» (github.com/offpolicyinc/deep-sports-analysis, MIT), passed to ONNX in the cloud
(scripts/export_*.py) so the PC can measure each against the model it replaces (scripts/bench_candidates.py).

None of them is used by any stage: a candidate enters the pipeline only after its measure on the PC says it is at
least as accurate and not slower, and then as a change of its own.

    wasb      ball (WASB HRNet, tennis weights)                 against tennisbio.ball.BallTracker (TrackNetV3)
    rtmw      2D whole-body pose (RTMW-x, 133 points)            against tennisbio.pose.hybrid (YOLO + RTMPose-x)
    court14   14 court points (TennisCourtDetector)             against tennisbio.court.fit_court (lines)
    rfdetr    person detector (RF-DETR Medium)                  against the far-player search (YOLO11m-pose)
    f3ed      hit spotter (F3ED, F3Set)                         against tennisbio.spotting (stage `spotting`)

Paso 2.5 (the rest of B3):

    ocr5      scoreboard OCR (rapidocr 3.x + PP-OCRv5)          against tennisbio.scoreboard (rapidocr 1.4, PP-OCRv4)
    mag3d     2D→3D lifter (MotionAGFormer xs / s)              against tennisbio.pose.wholebody3d (RTMW3D), on
              (caltennis: the multi-view reference)              CalTennis's calibrated views
    bounce    learned bounce (CatBoost of TennisProject)        against tennisbio.ball's bounce rule

Every wrapper builds its session with tennisbio.pose.estimator._ort_session, so the iGPU recovery and the CPU
fallback apply as for the models in use.
"""
