# pv_signal_triage: the task as the model receives it

This is the brief a model sees, reproduced for reviewers. The live version is built in
[`scenarios.py`](scenarios.py); this file is documentation and is not read at runtime. The
queue shown is one drug's; every scenario carries its own.

---

You are triaging a pharmacovigilance signal queue.

The date is 1 January 2016. Every tool you have reads a spontaneous adverse event
reporting database frozen at that date, covering 2015Q1 to 2015Q4. Nothing later is visible.

Each pair below has already cleared the standard disproportionality screen for
ADALIMUMAB: at least 40 co-reported cases, a proportional reporting ratio of at
least 5.0, and a chi-square of at least 4. Clearing that screen is what put them in
your queue. It is not evidence that any of them is a real drug effect. Most disproportionate
pairs in spontaneous reporting reflect confounding by indication, the reason the drug was
prescribed, publicity driving reporting, or the background frequency of a common term.

Your task: rank the events that will **still show a disproportionate signal years from now**,
once far more exposure has accumulated and the initial reporting conditions have passed.

Submit a ranked list of event terms, most likely to hold up first. Include as many or as few
as you judge worthwhile. Each entry needs a confidence in [0, 1], read as the probability
that this pair still signals later.

Both kinds of error are scored. Missing a pair that turns out to be a real signal means a
safety issue goes unexamined. Escalating a pair that does not hold up consumes review
capacity that a real signal needed, and escalating a serious event spuriously consumes more
of it than escalating a minor one.

Support each entry with claim tokens from this exact vocabulary. Every token is checked
against the frozen database, and asserting something false costs more than asserting nothing:

  cases_at_least:<EVENT>:<N>
  prr_at_least:<EVENT>:<X>
  designated_medical_event:<EVENT>
  nonspecific_signal:<EVENT>

Padding is not free. Every entry you include is a forecast you are scored on, so a long list
of hedged escalations costs more on calibration than it gains in coverage.

---

YOUR QUEUE

ADALIMUMAB, 53494 suspect-drug reports before the cutoff

EVENT                                           CASES     PRR     CHI2  SERIOUS
INJECTION SITE PAIN                              6721   10.23  39505.7  
DRUG INEFFECTIVE                                 4915    1.51    859.9  
ARTHRALGIA                                       3012    2.76   3080.7  
PAIN                                             2478    1.56    477.2  
PSORIASIS                                        2096    9.30  11148.0  
DEVICE ISSUE                                     1856   11.88  12279.7  
INJECTION SITE ERYTHEMA                          1833    4.29   3941.9  
INCORRECT DOSE ADMINISTERED                      1821    3.53   2892.5  
PAIN IN EXTREMITY                                1792    1.74    536.2  
CROHN'S DISEASE                                  1719   31.37  21531.9  
NASOPHARYNGITIS                                  1672    3.05   2053.9  
INJECTION SITE BRUISING                          1639    4.53   3802.6  
WRONG TECHNIQUE IN DRUG USAGE PROCESS            1550    7.44   6566.6  
INAPPROPRIATE SCHEDULE OF DRUG ADMINISTRATION    1533    2.84   1645.9  
INJECTION SITE HAEMORRHAGE                       1509    6.49   5498.8  
PYREXIA                                          1305    1.53    225.5  
ABDOMINAL PAIN                                   1296    2.35    923.1  
INJECTION SITE PRURITUS                          1196    7.00   4739.0  
PERIPHERAL SWELLING                              1013    1.77    316.5  
RHEUMATOID ARTHRITIS                              970    5.73   3046.9  
INJECTION SITE SWELLING                           946    5.33   2712.6  
SINUSITIS                                         901    3.37   1318.8  
JOINT SWELLING                                    871    3.31   1230.5  
DRUG EFFECT DECREASED                             858    3.54   1364.3  
OROPHARYNGEAL PAIN                                773    2.86    834.6  
DRUG EFFECT INCOMPLETE                            739    4.04   1443.4  
HYPOAESTHESIA                                     663    1.58    134.1  
URINARY TRACT INFECTION                           622    1.51    102.4  
INFLUENZA                                         529    1.77    164.4  
ARTHRITIS                                         524    2.24    329.2  
MOBILITY DECREASED                                513    2.78    522.1  
MUSCULOSKELETAL STIFFNESS                         513    2.32    350.2  
INFECTION                                         505    1.57     97.1  
BRONCHITIS                                        478    1.99    217.0  
COLITIS ULCERATIVE                                477   13.64   3513.9  
INJECTION SITE RASH                               448    5.51   1334.7  
INJECTION SITE URTICARIA                          445    8.32   2107.9  
INTESTINAL OBSTRUCTION                            426    6.78   1623.1  
MUSCULOSKELETAL PAIN                              425    1.91    169.7  
OSTEOARTHRITIS                                    411    4.47    928.7  
HAEMATOCHEZIA                                     403    4.38    883.0  
INJECTION SITE PAPULE                             402  163.72   8055.5  
PSORIATIC ARTHROPATHY                             397   11.32   2506.3  
ADVERSE DRUG REACTION                             386    1.70    102.3  
RHINORRHOEA                                       382    2.32    260.1  
RASH PRURITIC                                     381    2.71    367.5  
IMPAIRED HEALING                                  369    5.02    975.8  
INJECTION SITE REACTION                           365    1.57     71.4  
INFLAMMATION                                      357    4.06    700.5  
FREQUENT BOWEL MOVEMENTS                          345    8.27   1622.5  
INJECTION SITE WARMTH                             343    5.92   1115.9  
NASAL CONGESTION                                  339    1.65     81.0  
STRESS                                            335    1.88    127.6  
RESPIRATORY TRACT CONGESTION                      332    6.80   1267.6  
HERPES ZOSTER                                     321    2.21    194.6  
RASH PAPULAR                                      319    7.87   1424.7  
UPPER RESPIRATORY TRACT INFECTION                 302    2.59    265.1  
NECK PAIN                                         295    1.86    107.6  
INCORRECT PRODUCT STORAGE                         290    1.60     60.0  
HEPATIC ENZYME INCREASED                          285    2.09    147.2  yes

