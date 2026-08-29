# Methodology

## 1. The Pilot Corpus

The pilot corpus comprises 29 works totalling 2,371,796 words as recorded in the corpus manifest (Table 1): 26 Byzantine texts spanning the seventh to twelfth centuries and three ancient control texts. The Byzantine material divides chronologically into a seventh–eighth-century layer (Stephanus of Alexandria, the *Doctrina Patrum*, Maximus the Confessor, John of Damascus), a ninth–tenth-century layer (Photius, Arethas of Caesarea), and an eleventh–twelfth-century layer that carries the analytical weight of the pilot: the commentaries of Eustratius of Nicaea — the target of both case studies — alongside Michael Psellos, Michael of Ephesus, and Nicholas of Methone. The three ancient controls (Plato, *Respublica*; Aristotle, *Ethica Nicomachea*; Proclus, *In Rempublicam*) were selected to cover the source traditions most heavily quarried by the Byzantine corpus: the Platonic and Aristotelian base texts of the commentary tradition, and the Neoplatonic exegesis whose covert afterlife Case Study A investigates.

| ID | Author | Work | Edition | Source | Words |
|---|---|---|---|---|---|
| **Ancient controls** | | | | | |
| tlg0059.tlg030 | Plato | *Respublica* | Burnet 1902 (OCT) | OGL (Perseus) | 88,543 |
| tlg0086.tlg010 | Aristotle | *Ethica Nicomachea* | Bywater 1894 (OCT) | OGL (Perseus) | 56,595 |
| tlg4036.tlg001 | Proclus | *In Platonis Rem publicam commentarii* | Kroll 1899–1901 (Teubner) | Scaife | 198,509 |
| **7th–8th c.** | | | | | |
| 9019.001 | Stephanus of Alexandria | *In De Interpretatione* | Hayduck 1885 (CAG 18.3) | TLG | 23,322 |
| 7051.001 | anon. | *Doctrina patrum de incarnatione verbi* | Diekamp 1981 | TLG | 53,846 |
| 2892.001 | Maximus the Confessor | *Quaestiones ad Thalassium* | Laga–Steel 1980–90 (CCSG) | TLG | 75,560 |
| 2892.044 | Maximus the Confessor | *Epistulae* | PG 91 | OCR (PG) | 89,771 |
| 2892.050 | Maximus the Confessor | *Ambigua ad Thomam* | Janssens 2002 (CCSG) | OCR | 8,158 |
| 2934.004 | John of Damascus | *Expositio fidei* | Kotter 1973 (PTS) | TLG | 57,349 |
| 2934.002 | John of Damascus | *Dialectica* | Kotter 1969 (PTS) | TLG | 20,618 |
| **9th–10th c.** | | | | | |
| 4040.001 | Photius | *Bibliotheca* | Henry 1959–77 / PG 101–104 | TLG | 324,266 |
| 2130.038 | Arethas of Caesarea | *Scholia in Porphyrii Isagogen* | Busse 1894 (CAG 4.1) | OCR (CAG) | 164,413 |
| 2130.039 | Arethas of Caesarea | *Scholia in Categorias* | Busse 1894 (CAG 4.1) | OCR (CAG) | 160,390 |
| **11th–12th c.** | | | | | |
| 4031.002 | Eustratius of Nicaea\* | *In Ethica Nicomachea I* | Heylbut 1892 (CAG 20) | TLG | 42,116 |
| 4031.003 | Eustratius of Nicaea\* | *In Ethica Nicomachea VI* | Heylbut 1892 (CAG 20) | TLG | 55,673 |
| 4031.001 | Eustratius of Nicaea\* | *In Analytica Posteriora II* | Heylbut 1907 (CAG 21.1) | TLG | 97,907 |
| 2702.012 | Michael Psellos\* | *Theologica I* | Gautier 1989 (Teubner) | TLG | 131,654 |
| 2702.010 | Michael Psellos | *Philosophica minora I* | O'Meara 1989 | TLG | 81,807 |
| 2702.011 | Michael Psellos | *Philosophica minora II* | O'Meara 1992 | TLG | 43,810 |
| 2702.028 | Michael Psellos | *De omnifaria doctrina* | PG 122 / Westerink 1948 | OCR (PG) | 62,838 |
| 4034.001 | Michael of Ephesus | *In EN IX–X* | Heylbut 1892 (CAG 20) | TLG | 59,144 |
| 4034.006 | Michael of Ephesus | *In EN V* | Heylbut 1892 (CAG 20) | TLG | 26,142 |
| 4034.002 | Michael of Ephesus | *In Parva Naturalia* | Wendland 1903 (CAG 22) | TLG | 45,490 |
| 4034.003 | Michael of Ephesus | *In De partibus animalium* | Hayduck 1904 (CAG 22) | TLG | 36,724 |
| 4034.004 | Michael of Ephesus | *In De animalium motione* | Hayduck 1904 (CAG 22) | TLG | 8,690 |
| 4034.005 | Michael of Ephesus | *In De animalium incessu* | Hayduck 1904 (CAG 22) | TLG | 12,270 |
| 0732.004 | Michael of Ephesus (trad. Alex. Aphr.) | *In Metaphysica* | Hayduck 1891 (CAG 1) | TLG | 303,072 |
| 3104.005 | Nicholas of Methone | *Adv. Latinos de spiritu sancto* | PG 133 | OCR (PG) | 15,936 |
| 3104.006 | Nicholas of Methone | *Adv. Latinos de azymis* | PG 133 | OCR (PG) | 27,183 |

\* Case-study texts: the three Eustratius commentaries are the target of both case studies; Psellos's *Theologica* I is the principal source text of Case Study B. Proclus's *In Rempublicam*, the source text of Case Study A, additionally serves as an ancient control (see §4.2 on this dual role).

All texts derive from the standard critical editions. Digital text was obtained from TLG-derived sources, from Open Greek and Latin (Perseus) and the Scaife Viewer for the redistributable ancient texts, or produced by OCR from open-access scans of the CAG and Patrologia Graeca where no digital text was available. The corpus manifest (`corpus_manifest.yaml`), released with the data archive, records edition, provenance, and word count for every work; because raw TLG text cannot be redistributed, the archive identifies TLG-derived works by canonical identifier and citation coordinates, from which the corpus is reproducible under an institutional TLG subscription.

## 2. Prior Text Reuse Detection Tools

Computational text reuse detection in ancient-language corpora is an established field, and the pipeline presented here is positioned against its principal systems.

**TRACER** (Büchler et al., 2014) is the most general framework: a modular architecture of candidate retrieval by n-gram fingerprinting, alignment, and post-processing, applied to both Latin and Greek corpora. Its flexibility is also its cost — meaningful results require extensive per-corpus configuration, and its linguistic post-processing layers presuppose stable orthography and usable lemmatization, neither of which holds for Byzantine commentary Greek. **Passim** (Smith, Cordell and Mullen, 2015), developed for reprinted texts in antebellum American newspapers, detects reuse at paragraph granularity via skip-grams and Jaccard similarity, scaling to very large collections. Its granularity suits near-verbatim reuse of substantial passages, but Byzantine philosophical borrowing typically consists of chains of four to twelve words embedded in original framing prose — below Passim's natural resolution. **Tesserae** (Coffee et al., 2013; in its current service architecture Okuda et al., 2022) is purpose-built for literary allusion in classical poetry: it matches lemmatized n-grams and ranks the results by lexical rarity. Its dependence on lemmatization is precisely what excludes it here, since no lemmatizer reliably handles the morphology and vocabulary of Byzantine philosophical commentary: Vatri and McGillivray (2020), evaluating the available Ancient Greek lemmatizers on classical texts, documented the accuracy limits of the state of the art, and our own spot test on 500 Byzantine philosophical tokens produced error rates above 35%.

Closer in spirit to our problem is the **BIBLINDEX** project (Mellerin, 2014; Hue-Gay, Mellerin and Morlock, 2017), which indexes biblical text reuse across early Christian literature and has adapted TRACER to its corpus in collaboration with the eTRAP group (Büchler and Mellerin, eds., 2017). BIBLINDEX shares our structural situation — a canonical source corpus quoted pervasively by a later tradition — but its object is the explicit citation; ours is the covert borrowing that the citation traffic conceals. The **SAWS** project (Roueché, Searby, Wakelnig et al., 2013) mapped the transmission of Greek and Arabic gnomologia, demonstrating that anthological traditions transmit philosophical content through selection, reordering, and reattribution rather than copying — a model of mediated transmission that frames one of our stated limitations (§4.5). Finally, Moritz et al. (2016) and Manjavacas et al. (2019) established empirically that surface-form matching captures only a subset of reuse phenomena, with paraphrase and allusive reuse remaining open problems; this bounds what any pipeline of the present kind can claim.

Against this landscape, the present pipeline differs in three respects: a language-agnostic matching core requiring no lemmatization, with character-level fuzziness absorbing Byzantine orthographic variance; control-corpus filtering (§4.2) built into the detection pipeline as a first-class component rather than deferred to interpretation; and noise reduction targeted at the specific artifact classes of Byzantine digital editions.

## 3. FLAME: The Matching Engine

Text reuse is detected by FLAME (Fuzzy Levenshtein-tolerant Ancient Matching Engine), an n-gram chain aligner developed for morphologically rich historical languages and adapted from a sister project. FLAME performs an exhaustive all-pairs sweep: every comparison unit of every work is matched against every unit of every other work.

**Segmentation.** Each work is first stripped of three classes of non-authorial material: modern editorial metadata (CTS URNs, EpiDoc markup, Creative Commons licence strings, removed by pattern matching); critical-apparatus sigla (*om.*, *ss*, *m1* and similar, removed conservatively — only notations followed by a period or space delimiter — to avoid deleting genuine Greek or Latin words); and generic scholastic transition formulas (τοῦτο δὲ ταὐτόν ἐστι τῷ, ἐν δὲ τῇ λέξει, τὰ ἑξῆς), which are the structural furniture of line-by-line commentary rather than authorial content. The cleaned text is segmented into sliding windows of 140 words with a 25-word overlap, aligned where possible to sentence boundaries (Greek period ·, question mark ;, and the line conventions of the editions). The window size is a compromise: large enough to contain a complete argumentative period, small enough to keep accidental collocations from accumulating. No orthographic normalisation is applied beyond the Unicode standardisation of the source texts, and no lemmatization is performed; the comparison operates on surface forms throughout.

**Phase 1 — Tokenization.** Each unit is decomposed into character-level n-grams of length 4 (quadrigrams), and a hash is computed for each. Quadrigrams were chosen as the balance point: trigrams flood the candidate space of a highly formulaic language, while pentagrams begin to miss orthographically variant repetitions.

**Phase 2 — Candidate retrieval.** N-gram hash collisions between two units are clustered. Clusters below the `max_candidates` ceiling (default 4,000) pass to alignment; denser clusters indicate high-similarity unit pairs and are prioritised.

**Phase 3 — Chain alignment.** Within each cluster, character-level Levenshtein similarity is computed, and consecutive n-grams whose similarity meets the `fuzz_threshold` (default 0.75, i.e. at least 75% character overlap) are merged into chains. A chain thus represents a run of consecutively matching *words*, not raw character n-grams; chains shorter than `min_chain_words` (default 2) are discarded. Each n-gram tolerates at most one mismatched character, which is what absorbs the systematic orthographic variance of Byzantine transmission — itacism (η/ι/ει/οι), αι/ε confusion, movable ν, diacritic loss in OCR — without lemmatization or normalisation.

FLAME deliberately excludes gapped (non-adjacent) alignment: every element of a chain must be consecutive in both source and target. This prioritises precision over recall. It will miss paraphrastic reuse and reordered argument, but in a corpus dominated by commentary — where syntactic reordering is a routine rewriting strategy — admitting gaps multiplies false positives from commentary-specific syntax faster than it recovers genuine reuse.

For each match, FLAME records the work identifiers, citation-page references, a normalised similarity score, the chain length in words, the total matched tokens, the token range of the match within each citation-page unit, the matched snippets, and the chronological era of each side. Output is written to NDJSON and flat TSV. On the 29-work corpus, the sweep evaluated 406 work pairs in approximately 140 minutes on a standard workstation without GPU acceleration, and produced **35,753 raw matches**. All numerical claims in this paper are computed from this raw set by a single script (`compute_reported_numbers.py`), released with the archive together with its output (`reported_numbers.json`), which records input hashes and run date.

## 4. The Filtering Architecture

Raw string matching over a tradition this formulaic is dominated by philologically inert matches. The filtering architecture separates the two phenomena of interest — Byzantine reception of ancient sources, and covert inter-Byzantine borrowing — and removes, in a controlled and quantified way, everything else.

### 4.1 Partition of the raw match set

The 35,753 raw matches partition into three disjoint classes by the author identity of the two sides:

| Class | Definition | Matches |
|---|---|---|
| BYZ–ANC | Byzantine work × ancient control | 6,426 |
| BYZ–BYZ (same author) | Different works by one Byzantine author | 6,273 |
| BYZ–BYZ (different author) | Two distinct Byzantine authors | 23,054 |

Same-author matches are excluded from inter-author analysis by definition (an author repeating himself is not borrowing). The BYZ–ANC set is the raw material of the reception analysis; the different-author BYZ–BYZ set holds the candidates for inter-Byzantine borrowing.

### 4.2 The Topos Exclusion Matrix

The dominant source of false positives among the BYZ–BYZ candidates is the shared-ancient-source effect: two Byzantine authors who both quote *Categories* 1b10 produce a string match between each other that is in fact two independent citations of Aristotle. The pilot's diagnostic case was Stephanus of Alexandria (7th c.) and Eustratius (12th c.), who share the clause γὰρ πᾶς οὐ τὸ καθόλου σημαίνει ἀλλ' ὅτι καθόλου — verbatim *De Interpretatione* 17b12, not a Byzantine transfer.

The Topos Exclusion Matrix filters these cases using the control corpus, in four steps. First, FLAME is run between every Byzantine work and the three ancient controls, producing the BYZ–ANC match set (6,426 matches). Second, for each Byzantine work, the citation-page coordinates of all its BYZ–ANC matches are collected — the "hot coordinates," regions of the Byzantine text known to overlap ancient source material. Third, every BYZ–BYZ match is tested against these coordinates: if either Byzantine side's token range overlaps a hot coordinate on the same citation page, with overlap ratio at least `min_ratio` (default 0.50) of the match's own length, the match is tagged `ancient_commonplace`. Formally, a BYZ–BYZ match *M* whose Byzantine side *B* occupies token range *w_B* on citation page *p_B* is tagged iff there exists a control coordinate *c* on *p_B* with |*w_B* ∩ *c*| / |*w_B*| ≥ 0.50.

Applied to the full BYZ–BYZ set (29,327 matches), the filter tagged **11,487 matches (39.2%)** as ancient commonplaces, leaving a clean BYZ–BYZ remainder of 17,840. That over a third of raw string identity between Byzantine authors dissolves into shared reliance on three ancient works is itself a finding: it quantifies, for the first time on this corpus, how much of the apparent inter-Byzantine textual network is an artifact of common sources.

One design point requires explicit statement. Proclus's *In Rempublicam* plays a dual role: as a control text it supplies hot coordinates for the BYZ–BYZ filter, while Proclus–Byzantine matches are simultaneously the primary signal of the reception analysis (and of Case Study A). This is deliberate, not circular, because the two uses answer different questions. The filter asks whether a given Byzantine–Byzantine string match is explained by common ancient material; the reception analysis asks how Byzantine authors engage the ancient inheritance. A Proclus passage quoted independently by two Byzantines is a false positive for the first question and evidence for the second.

### 4.3 Work-package thresholds

The clean material then passes through thresholds calibrated per research strand. The BYZ–ANC matches feed the reception analysis in three chronological layers, at chain length ≥ 6 with a score floor of 0.001 for the seventh–tenth-century layers, and at the stricter chain ≥ 8 with score ≥ 0.01 for the eleventh–twelfth-century layer, whose lemma-dense commentaries generate proportionally more noise. This yields 7, 14, and 678 reception candidates respectively. The clean different-author BYZ–BYZ matches pass a chain ≥ 6 threshold — motivated by the chain-length distribution of the raw set, in which 86.3% of different-author matches fall below chain 6 and are overwhelmingly coincidental short-gram overlap — yielding the intra-Byzantine candidate set, to which a further 877 `ancient_commonplace`-tagged matches are deliberately restored (below), for an intra-Byzantine total of 4,561 and a pipeline total of **5,260 candidate matches**.

### 4.4 Retained commonplaces: why exclusion cannot be absolute

The 877 restored matches embody the architecture's most important refinement. "Commonplace" and "genuine reuse" are not disjoint categories: a Byzantine author can adopt an ancient lemma *and* wrap it in a distinctive syntactic or polemical frame which a later author then reproduces. In such a case the ancient core is common property — both authors could cite it independently — but the frame is a genuine vector of transfer, and a filter that discards the match on the strength of the core alone throws away the signal with the noise. Case Study B is exactly this configuration: the shared string is Aristotle's predication rule, tagged (correctly, at string level) as a commonplace, while the transferred object is Psellos's anti-Eunomian qualification of that rule. The tagged matches restored to the intra-Byzantine candidate set are therefore presented to the philologist for contextual evaluation rather than silently discarded, and the planned bidirectional refinement of the filter — distinguishing matches where both sides merely hit the control from matches where one side reframes it — is a direct methodological outcome of the pilot.

### 4.5 What the architecture does not decide

Three limits bound the pipeline's claims. Direction is supplied by chronology and context, never by the string evidence itself, so a common lost source or an intermediary — a florilegium of the kind whose transmission logic SAWS documented — can only be excluded by targeted controls, not by the cascade; the case studies accordingly specify collocational tests against the intervening commentary tradition and, for Case B, the Cappadocian anti-Eunomian corpus. Surface-form comparison under-detects inflectional variation and paraphrase (Moritz et al., 2016; Manjavacas et al., 2019). And every one of the 5,260 candidates is computational output, not a philological result: the pipeline's function is to reduce thirty-five thousand raw matches to a set small and clean enough to be read — which is where the philology begins.

## References

Büchler, M., Burns, P. R., Müller, M., Franzini, E. and Franzini, G. (2014). Towards a historical text re-use detection. In Biemann, C. and Mehler, A. (eds), *Text Mining: From Ontology Learning to Automated Text Processing Applications*. Springer, 107–126.

Büchler, M. and Mellerin, L. (eds.) (2017). Computer-aided processing of intertextuality in ancient languages [Special issue]. *Journal of Data Mining and Digital Humanities*.

Coffee, N., Koenig, J.-P., Poornima, S., Ossewaarde, R., Forstall, C. and Jacobson, S. (2013). The Tesserae Project: intertextual analysis of Latin poetry. *Literary and Linguistic Computing*, 28(2), 221–228.

Hue-Gay, E., Mellerin, L. and Morlock, E. (2017). TEI-encoding of text reuses in the BIBLINDEX Project. *Journal of Data Mining and Digital Humanities*.

Manjavacas, E., Kádár, Á. and Kestemont, M. (2019). On the feasibility of automated detection of allusive text reuse. *Proceedings of LaTeCH-CLfL 2019*, 143–152.

Mellerin, L. (2014). New ways of searching with Biblindex, the online index of biblical quotations in ancient Christian literature. In *Digital Humanities in Biblical, Early Jewish and Early Christian Studies*. Brill, 175–192.

Moritz, M., Wiederhold, A., Pavlek, B., Bizzoni, Y. and Büchler, M. (2016). Non-literal text reuse in historical texts. *Proceedings of EMNLP 2016*, 1849–1859.

Okuda, N., Kinnison, J., Burns, P. J., Coffee, N. and Scheirer, W. J. (2022). Tesserae Intertext Service. *Digital Humanities Quarterly*, 16(1).

Roueché, C., Searby, D., Wakelnig, E. et al. (2013). *Sharing Ancient Wisdoms: The SAWS Dynamic Library of Wisdom Literatures*. HERA project.

Smith, D. A., Cordell, R. and Mullen, A. (2015). Computational methods for uncovering reprinted texts in antebellum newspapers. *American Literary History*, 27(3), 563–580.

Vatri, A. and McGillivray, B. (2020). Lemmatization for Ancient Greek: an experimental assessment of the state of the art. *Journal of Greek Linguistics*, 20(2), 179–196.
