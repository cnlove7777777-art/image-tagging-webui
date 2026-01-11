DEFAULT_CAPTION_PROMPT = (
    "Generate a training caption for a photo-realistic portrait / cosplay photoshoot.\n"
    "Comma-separated short phrases in this exact order:\n"
    "subject (female model, count),\n"
    "face & body features,\n"
    "hair (style/color/length),\n"
    "makeup & expression (makeup style, micro-expression, gaze direction/target, mouth state),\n"
    "outfit (color/material/style),\n"
    "accessories,\n"
    "pose & action (body orientation, weight on which leg, head tilt, shoulder/hip angle, "
    "hand placement + finger shape, action verb + interaction target),\n"
    "setting/background,\n"
    "lighting (type, direction, softness, catchlights),\n"
    "composition & camera (shot, angle, focus point, lens/aperture vibe),\n"
    "mood & color tone.\n"
    "English first, allow a few Chinese phrases when helpful (\"日系写真\", \"窗边柔光\", \"干净背景\").\n"
    "Rules: be specific; omit unknown; no vague words; no meta words.\n"
    "Keep under 200 words.\n"
    "End with: tags: ... (10–25 tags, photography/lighting/lens/style focused)"
)

DEFAULT_DEDUP_PARAMS = {
    "face_sim_th1": 0.80,
    "face_sim_th2": 0.85,
    "pose_sim_th": 0.98,
    "face_ssim_th1": 0.95,
    "face_ssim_th2": 0.90,
    "bbox_tol_c": 0.04,
    "bbox_tol_wh": 0.06,
    "keep_per_cluster": 2,
}
