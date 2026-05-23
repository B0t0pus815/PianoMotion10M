# English Abstract

**Title**: AI Piano Learning: Integrating PianoMotion10M and ArLSTM Fingering Decisions via Dual-Track Decoupling

**Author**: [Student name] · **Advisor**: [Advisor name] · **Department**: [Department] · **Year**: 2026

---

Recent deep learning advances in music information retrieval have made AI-assisted music learning feasible. However, existing state-of-the-art works concentrate on individual aspects—piano hand motion generation (e.g., PianoMotion10M, Liu et al., 2024), automatic fingering decision (e.g., Ramoneda et al., 2022), or performance assessment—without integrating them into a complete teaching loop with quantitative justification.

This thesis addresses the integration research question: *Can we design an AI piano learning system in which the visual demonstration the student watches and the system's judgment of the student's performance share a single fingering decision source?* We propose a **Dual-Track Decoupling architecture** that separates fingering judgment from hand rendering: a deterministic neural model (Ramoneda's ArLSTM) acts as the Logic Track judge, while an anatomy engine (biomech v4) acts as the Visual Track renderer. The system is implemented in three stages: **Stage A** integrates ArLSTM behind a unified `generate_fingering(source='arlstm')` API; **Stage B** injects the ArLSTM-prescribed fingerings into the `simple_natural --fingering arlstm` rendering pipeline to produce videos; **Stage C** connects the rendered output to a React PracticeScreen UI the student actually uses.

To justify the Logic Track candidate selection, we design a **rule-based corpus evaluation framework** (`build_gt_rulebased.py`) that auto-generates ground truth using documented piano-pedagogy conventions, with a **predictor-neutral subset** mechanism to mitigate LLM-GT self-favoring bias. On the combined Canon RH+LH neutral subset (n=183), ArLSTM achieves Soft Accuracy **0.792**, significantly outperforming pianoplayer (0.578, -27% relative) and the motion-derived baseline (0.358, -55%). On the left hand alone, pianoplayer's Soft drops to 0.275—approaching random performance—providing direct evidence of Parncutt cost model's structural ring-finger atrophy. A cross-piece audit on Bach Invention No.1 reveals that ArLSTM is **not a universal winner**: on the continuous scalar passages of Bach's right hand, pianoplayer wins (Soft 0.734 vs 0.406). This nuance does not weaken the integration contribution; rather, it reinforces the runtime-switchable Logic Track design and motivates style-aware auto-switching as a direct future direction.

**Key contributions**: (1) The Dual-Track Decoupling architecture; (2) Integration of Ramoneda 2022 SOTA as the default Logic Track; (3) A rule-based corpus GT framework with a predictor-neutral subset; (4) End-to-end Stage A→B→C pipeline validated on three stylistically distinct pieces (Canon, Summer, Bach Invention); (5) Quantitative evidence revealing cost-model's structural LH bias and SOTA neural model's cross-style limitations.

**Keywords**: AI music education, piano fingering decision, Dual-Track architecture, PianoMotion10M, Ramoneda 2022 ArLSTM, real-time performance feedback, Stage A/B/C integration
