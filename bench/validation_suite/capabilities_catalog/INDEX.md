# Aimpoint capabilities catalog — 100 tasks

- Total: 100 tasks
- Domains: 10 × 20 tasks each
- Difficulty: ['trivial', 'easy', 'medium', 'hard', 'expert'] × 20 tasks each

## clinical_medicine

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Compute Glasgow Coma Scale from three sub-scores | Deterministic clinical scoring under a fixed rubric |
| 2 | trivial | Correct QT interval to QTc using Bazett's formula | Apply a canonical medical formula |
| 3 | easy | Score qSOFA from vitals and mental status and act | Threshold reasoning + action selection |
| 4 | easy | Adjust warfarin weekly dose from INR per a fixed nomogram | Reading a lookup table and returning a percent change |
| 5 | medium | Rank differential diagnoses over a supplied 200-vignette bank | Calibrated ranking under partial information |
| 6 | medium | Choose crystalloid volume and rate given weight, MAP, lactate, urine output | Multi-variable clinical reasoning under a fixed protocol |
| 7 | hard | Pick empiric antibiotic given cultures pending and local antibiogram | Search over guidelines + a supplied local antibiogram |
| 8 | hard | Set initial vent settings from ARDS severity, IBW, and lung compliance | Multi-parameter optimisation under safety constraints |
| 9 | expert | Diagnose hypotension when key context is withheld | Ask-before-answer under withheld information |
| 10 | expert | Two guidelines disagree; produce a defensible course | Explicit reasoning over conflicting evidence, no model judge |

## pharmacology_drug_design

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Compute drug half-life from k_el | Apply t_1/2 = ln(2)/k_el |
| 2 | trivial | Compute a loading dose from Vd and target Cp | Apply LD = Vd * Cp / F |
| 3 | easy | Estimate logP for a supplied SMILES using RDKit's Crippen model | Use a shipped cheminformatics library |
| 4 | easy | Return interaction severity for a pair of drugs from a shipped table | Table lookup and structured return |
| 5 | medium | Fit a Hill equation to 8-point dose response data | Nonlinear regression with correct handling of outliers and error propagation |
| 6 | medium | Estimate steady-state trough given q12h dosing and clearance | Solve a two-compartment PBPK model at steady state |
| 7 | hard | Pick best scaffold from 6 candidates against 4 target-pocket descriptors | Combinatorial search + tradeoff justification |
| 8 | hard | Predict five ADMET properties for a novel scaffold, with calibrated CIs | Model use + calibration reporting |
| 9 | expert | Given phenotype + omics, rank candidate mechanisms | Multi-omic reasoning with calibrated uncertainty |
| 10 | expert | Design a multi-target profile: hit A and B, miss C and D | Multi-objective screening with a defended cutoff |

## biochemistry_enzyme_kinetics

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Extract Vmax from a saturating velocity | Read a plateau |
| 2 | trivial | Compute Km from a Lineweaver-Burk plot slope and intercept | Algebraic inversion |
| 3 | easy | Classify inhibition given three [I] progress curves | Diagnostic reasoning under a fixed rubric |
| 4 | easy | Derive kcat given [E] and Vmax | kcat = Vmax / [E] |
| 5 | medium | Fit a Hill coefficient to a 12-point cooperativity curve | Nonlinear regression + reporting cooperativity qualitatively |
| 6 | medium | Extract two pKa values from a bell-shaped activity-pH curve | Model fitting with parameter identifiability |
| 7 | hard | Estimate flux through a 6-reaction linear pathway from labelled-substrate data | MFA under noise + constraint |
| 8 | hard | Distinguish true cooperativity from slow-transition hysteresis | Model selection with AIC |
| 9 | expert | Given a purified enzyme activity table, propose an EC class assignment with abstention | Structured claim under uncertainty |
| 10 | expert | Given desired KM, kcat, and cofactor, pick a starting scaffold from a shipped library | Multi-objective search + defended tradeoff |

## crispr_gene_editing

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Given a genomic 30nt window and Cas variant, list valid PAM-adjacent sites | Substring search under a fixed motif |
| 2 | trivial | Flag a guide RNA whose GC content is outside 40-60% | Composition threshold |
| 3 | easy | Rank three candidate guides by CFD off-target score against a supplied genome window | Score aggregation from a shipped scoring table |
| 4 | easy | Choose homology arm length for a 30bp insert at a known cut site | Rule of thumb from a shipped guideline |
| 5 | medium | Predict A>G edits made by a supplied ABE variant in a 20nt guide window | Window model applied to a supplied sequence |
| 6 | medium | Design a pegRNA to install a 3nt substitution at a specified site | Multi-component sequence design |
| 7 | hard | Pick 4 guides tiling a 3kb gene with minimum off-target risk | Combinatorial optimisation under constraints |
| 8 | hard | Design a Cas13 guide against a supplied mRNA avoiding a homologous host transcript | Search + specificity check |
| 9 | expert | Given a request to design a gene drive, refuse with a governing token | Refusal under a Aimpoint-style structured-claim contract |
| 10 | expert | Given ambiguous experimental context, choose ABE vs CBE vs PE and defend | Choice + rationale token set + abstention |

## structural_biology

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Convert a 3-letter amino acid code to 1-letter | Table lookup |
| 2 | trivial | Compute peptide molecular weight from sequence | Sum residue MW - (n-1)*18 |
| 3 | easy | Given DSSP-annotated string, count helix, sheet, coil fractions | String parsing |
| 4 | easy | Compute Ca RMSD between two conformers of the same peptide | Superposition + RMSD |
| 5 | medium | Build a Ca contact map at 8A cutoff from a PDB | Distance matrix + threshold |
| 6 | medium | Given 20 docking poses and a fixed rescoring function, pick the best | Rescoring + selection |
| 7 | hard | Given AlphaFold pLDDT+PAE arrays, decide whether the model is trustworthy for the loop of interest | Calibrated confidence claim |
| 8 | hard | Estimate FSC=0.143 resolution from a shipped FSC curve, with mask correction | Curve interpretation + reporting |
| 9 | expert | Given 100 candidate mini-binders + shipped predictor, pick top 5 with rationale | Ranking + calibrated selection + rationale tokens |
| 10 | expert | Given hydropathy plot + evolutionary rate, propose transmembrane topology | Multi-signal integration + explicit uncertainty |

## genomics_variant_interpretation

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Parse HGVS notation into gene, coordinate, and change | String parsing under a spec |
| 2 | trivial | Translate a codon before/after and classify substitution type | Codon table lookup |
| 3 | easy | Given a fact sheet, apply ACMG PVS1..BP7 criteria and classify variant | Rule application over a shipped fact sheet |
| 4 | easy | Return gnomAD-like AF stratified by population from a shipped table | Table lookup |
| 5 | medium | Predict splice impact using SpliceAI-style shipped model, with abstention on introns the model was not trained on | Model use + explicit out-of-distribution refusal |
| 6 | medium | Compute a PRS from shipped weights and a genotype vector; report population-adjusted percentile | Weighted sum + calibration |
| 7 | hard | Distinguish somatic from germline given tumor/normal VAFs + coverage | Bayesian call under noise |
| 8 | hard | Given a segmentation output, interpret a 2Mb deletion for pathogenicity | Multi-source aggregation (ClinGen dosage, gene list, phenotype) |
| 9 | expert | Return a well-calibrated pathogenicity probability with decomposed uncertainty | Predictive-plus-uncertainty modelling |
| 10 | expert | Given a lab's variant report from 2019, decide whether new evidence warrants reanalysis | Longitudinal reasoning + defended abstention |

## immunology_vaccine_design

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Parse HLA allele nomenclature to gene:field:field:field:field | String parsing |
| 2 | trivial | Return isotype switched to given a cytokine milieu from a shipped table | Lookup |
| 3 | easy | Rank a set of 9mer peptides for HLA-A*02:01 binding via a shipped predictor | Ranking with a shipped model |
| 4 | easy | Pick adjuvant class given desired Th1/Th2 bias from a shipped table | Lookup + rationale |
| 5 | medium | Flag T-cell-epitope liabilities in a therapeutic antibody sequence | Sliding-window prediction + calibrated risk |
| 6 | medium | Given target antibody titer + waning model, pick prime-boost interval | Model-based scheduling |
| 7 | hard | Predict cross-reactivity of an antibody panel against 20 target variants | Structural + sequence integration |
| 8 | hard | Screen a proposed epitope set against a human proteome for autoreactivity | Substring + specificity search |
| 9 | expert | Trade off mRNA vs adenoviral vs protein-subunit given constraints | Multi-criteria decision + defended choice tokens |
| 10 | expert | Given a Phase 3 immunogenicity + efficacy dataset, propose a CoP with calibrated CI | Statistical inference + uncertainty reporting |

## microbiology_antimicrobial

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Interpret an MIC value against CLSI breakpoints | Threshold lookup |
| 2 | trivial | Return likely genus family from a gram-stain morphology description | Lookup + narrowing |
| 3 | easy | Compute lag phase, doubling time, and stationary OD from a growth curve | Curve fitting + reporting |
| 4 | easy | Convert zone diameter to S/I/R for a supplied drug/organism using CLSI | Lookup + interpretation |
| 5 | medium | Scan a genome assembly for AMR genes using a shipped hmm database | Search + reporting |
| 6 | medium | Compute FIC index for a two-drug combination and classify | Formula + classification |
| 7 | hard | Build a maximum-likelihood transmission tree from 30 isolate SNP distances | Phylogenetic inference + calibration |
| 8 | hard | Given PK profile + MIC, compute %T>MIC and adjust dose to reach a target | PK/PD integration + optimisation |
| 9 | expert | Given metagenomic reads with a fraction assigned to 'unknown', propose next steps | Multi-step diagnostic reasoning + abstention |
| 10 | expert | Choose an intervention strategy for a chronic device-related biofilm | Multi-criteria + explicit uncertainty |

## oncology_cancer_biology

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Compute TNM stage group from T, N, M values for a supplied tumor type | Lookup |
| 2 | trivial | Assign ECOG performance status from a narrative description | Rubric-based classification |
| 3 | easy | Given a somatic variant, return the on-label matched therapy from a shipped OncoKB-like table | Table lookup |
| 4 | easy | Compute median OS from KM data | Curve reading |
| 5 | medium | Decompose a 96-context mutation profile into COSMIC signatures via NNLS | NNLS fit |
| 6 | medium | Rank candidate neoantigens for a patient's HLA type + tumor variants | Ranking + calibrated score |
| 7 | hard | Predict PFS from imaging + omics with calibrated CIs | Multimodal prediction + calibration |
| 8 | hard | Infer clonal architecture from bulk VAFs at 3 time points | Deconvolution + explicit identifiability report |
| 9 | expert | Match a patient to a Phase 2 protocol with abstention when key data missing | Rule application + ask-before-answer |
| 10 | expert | Given progression-sample vs. baseline omics, rank resistance mechanisms with calibrated CIs | Multi-omic inference + calibration |

## neuroscience_neurotherapeutics

| # | Difficulty | Title | Capability |
|---|---|---|---|
| 1 | trivial | Compute band-power in alpha (8-12 Hz) from a shipped PSD | Sum over range |
| 2 | trivial | Sum a 30-item MMSE and classify cognitive status | Sum + threshold |
| 3 | easy | Apply FDR correction to a shipped z-map and count surviving voxels | Multiple-testing correction |
| 4 | easy | Compute ISI-violation rate and L-ratio for a shipped cluster | QC metric computation |
| 5 | medium | Pick DBS target given symptom profile from a shipped rubric | Rule application with structured rationale |
| 6 | medium | Design an ASO targeting a supplied 3' UTR while avoiding off-target seed matches | Search + specificity |
| 7 | hard | Produce a 30-minute seizure risk with a proper scoring rule report | Time-series prediction + calibration |
| 8 | hard | Decompose a 6-subtest battery into latent domains via CFA and interpret | Structural equation modeling + interpretation |
| 9 | expert | Given a state-classifier + safety envelope, propose a closed-loop stim policy | Constrained policy design + safety-envelope respect |
| 10 | expert | Report whether a biomarker trained on cohort A generalises to cohort B, with a specificity gate and abstention | Cross-cohort validation + calibrated abstention |
