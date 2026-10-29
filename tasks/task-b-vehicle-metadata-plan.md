# Vehicle metadata recovery implementation plan

2026-10-29, fresh post-PR14 branch. Primary implementation reference only;
no vehicle execution or fleet physical validation.

1. Trace the supplied coding APK's complete BMWSeries category catalogue and
   vehicle-order display consumers with REA. Do not fabricate a trim/model
   lookup or DoIP address mapping when those branches are absent.
2. Trace `y0.c/d/a` equipment-code selection and English labels, recover the
   exact `P` rows from the original encrypted `assets/salapa.enc`, and retain
   original/plain/generated hashes and row accounting.
3. Add a reproducible development-only extraction script, standalone bounded
   runtime English metadata asset and cached lookup module. Unknown codes remain
   explicit, with no German fallback or research tool runtime dependency.
4. The parent increment integrates the helper in the background vehicle-order
   read and renders the settled result. Run one-off exact/unknown/duplicate/type
   checks, reproduction checks and the full repository preflight gate.
