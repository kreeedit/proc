---
title: "Computational Detection of Implicit Philosophical Authority in Eustratius of Nicaea"
author: Jonathan Greig (HU Berlin/KU Leuven) / Tamás Kovács (Uni. Graz)
date: [Last revised 03. Aug. 2026; pre-print]
keywords: [Digital Humanities, Eustratius of Nicaea, Proclus, Michael Psellos, text re-use, Aristotle]
abstract:
    [TBD]
mainfont: Brill
fontsize: 11pt
documentclass: article
pdf-engine: xelatex
geometry:
  - margin=1.2in
numbersections: false
papersize: a4
secnumdepth: 1
citecolor: black
linkcolor: black
---

# 1. Introduction

In recent scholarship on Byzantine philosophy, influenced by recent work on late antique commentators on Aristotle and Plato, there has been growing interest in the implicit---besides known, explicit---uses of ancient philosophical authorities.[^epistauth-lit] These explicitly-cited authorities have been well-documented in the scholarship and in the indices nominum of published critical editions of Byzantine commentaries, going back to the mid- to late nineteenth century. Detecting implicit authorities, however, has remained a piecemeal project, especially over the last few decades. One example is the tracing of the late Neoplatonist Proclus' influence in John Italos, Michael Psellos, and, most recently, the twelfth-century bishop and philosopher Eustratius of Nicaea---work that has yielded breakthrough findings, such as Eustratius' dependence on Proclus in his commentaries on Aristotle, a dependence the late nineteenth- and early twentieth-century editors of these texts did not note in their indices or apparatus criticus. A broader picture of this engagement, beyond any one Byzantine philosopher, remains a desideratum: individual studies will, over time, contribute pieces to the desired map, but mapping the specific sites of implicit ancient engagement at scale would give the field a much-needed jump-start toward sustained, close study of these areas. A text re-use methodology capable of capturing these implicit references, verified and refined by trained Byzantine and ancient-philosophical philologists, would take the field considerably further toward this outcome.

In this paper, we take Eustratius of Nicaea as a test case, focusing on his engagement with Aristotle in his commentaries on Aristotle's *Nicomachean Ethics* I and *Posterior Analytics* II, as mediated through two distinct authorities: the 5th-century Neoplatonist Proclus, and the eleventh-century Byzantine philosophical predecessor of Eustratius, Michael Psellos. Eustratius' use of Proclus is, as noted, already established in the scholarship, and some work has begun to trace his implicit response to Psellos; but a complete accounting of Eustratius' implicit citations of Proclus remains undone, and how he draws on Psellos---particularly his argumentative framing---has been documented still less. While Proclus' influence in Eustratius has already been established, identifying the specific *loci* at which this influence is textually identified is still a work-in-progress: i.e., the precise formulations Eustratius draws from Proclus (such as Proclus' *In Rempublicam*, as we will discuss below) as distinct from material that he inherits from the wider, late antique commentary tradition. It is this gap, between the fact of dependence and its verifiable textual instantiation, that a computational approach is suited to close, and our first case study addresses it directly, revealing specific textual parallels not recognized so far in the literature on Eustratius' Neoplatonic sources. Psellos brings a different, comparatively neglected dimension of implicit authority into view: namely, the transmission of a near-contemporary Byzantine one. Eustratius' debt to Psellos shows that the authorities shaping his engagement with Aristotle were not only ancient, but also internal to the Byzantine tradition---inherited readings and argumentative strategies absorbed with the same silence usually reserved for ancient, pagan sources. This matters beyond Eustratius alone. Understanding how Byzantine philosophers drew on, cited, and reworked ancient authorities---Proclus being one important source among several---means attending as much to their engagement with one another as to their engagement with antiquity itself.

It is for locating this kind of implicit engagement---at specific, verifiable textual sites, whether the source is ancient or Byzantine---that a text re-use methodology is suited: run across a corpus at once, it surfaces candidates for philological verification rather than requiring the philologist to already suspect where to look. This does not replace close reading; it changes its scale.

We present this methodology (§2--5) and apply it to Eustratius as a test case (§6), treating the results as a graded set of findings, from confirmed dependence to genuinely open candidates (§7), before considering what the pilot establishes for scaling to the fuller seventh- to twelfth-century corpus (§8).

# 2. Current Work

We situate our approach first against existing computational tools (§2a), then against the philological scholarship on Eustratius' sources specifically (§2b).


## 2a. Computational Text Reuse Detection and Byzantine Sources

Computational text reuse detection in ancient-language corpora is an established field, and the pipeline presented here is positioned against its principal systems.

**TRACER** (Büchler et al., 2014) is the most general framework: a modular architecture of candidate retrieval by n-gram fingerprinting, alignment, and post-processing, applied to both Latin and Greek corpora. Its flexibility is also its cost---meaningful results require extensive per-corpus configuration, and its linguistic post-processing layers presuppose stable orthography and usable lemmatization, neither of which holds for the kind of Greek in Byzantine commentaries. **Passim** (Smith, Cordell and Mullen, 2015), developed for reprinted texts in antebellum American newspapers, detects reuse at paragraph granularity via skip-grams and Jaccard similarity, scaling to very large collections. Its granularity suits near-verbatim reuse of substantial passages, but Byzantine philosophical borrowing typically consists of chains of four to twelve words embedded in original framing prose --- below Passim's natural resolution. **Tesserae** (Coffee et al., 2013; in its current service architecture Okuda et al., 2022) is purpose-built for literary allusion in classical poetry: it matches lemmatized n-grams and ranks results by lexical rarity. Its dependence on lemmatization is precisely what excludes it here, since no lemmatizer reliably handles the morphology and vocabulary of Byzantine philosophical commentary: Vatri and McGillivray (2020), evaluating available Ancient Greek lemmatizers on classical texts, documented the accuracy limits of the state of the art, and our own spot test on 500 Byzantine philosophical tokens produced error rates above 35%.

Closer in spirit to our problem is the **BIBLINDEX** project (Mellerin, 2014; Hue-Gay, Mellerin and Morlock, 2017), which indexes biblical text reuse across early Christian literature and has adapted TRACER to its corpus in collaboration with the eTRAP group (Büchler and Mellerin, eds., 2017). BIBLINDEX shares our structural situation --- a canonical source corpus quoted pervasively by a later tradition --- but its object is the explicit citation; ours is the covert borrowing that citation traffic conceals. The **SAWS** project (Roueché, Searby, Wakelnig et al., 2013) mapped the transmission of Greek and Arabic gnomologia, demonstrating that anthological traditions transmit philosophical content through selection, reordering, and reattribution rather than copying --- a model of mediated transmission that frames one of our stated limitations (§5.5). Finally, Moritz et al. (2016) and Manjavacas et al. (2019) established empirically that surface-form matching captures only a subset of reuse phenomena, with paraphrase and allusive reuse remaining open problems; this bounds what any pipeline of the present kind can claim.

Against this landscape, the present pipeline differs in three respects: a language-agnostic matching core requiring no lemmatization, with character-level fuzziness absorbing Byzantine orthographic variance; control-corpus filtering (§5.2) built into the detection pipeline as a first-class component rather than deferred to interpretation; and noise reduction targeted at the specific artifact classes of Byzantine digital editions.

## 2b. Current Scholarship on Eustratius' Sources

The most substantive work that has been done on Eustratius---particularly Eustratius' dependence on Proclus---is Michele Trizio's 2016 monograph, *‌Il neoplatonismo di Eustrazio di Nicea*. Trizio establishes that Eustratius often depended on Proclus to explain Aristotle's text, as well as to mark out points of dispute whenever Aristotle critiqued Platonist positions, such as in *Nicomachean Ethics* I.6[^trizio-eust1]---here effectively following Proclus' specific critiques of Aristotle in contrast to the concordism of fifth--sixth-century Alexandrian Platonists, like Ammonius and Simplicius.[^alex-plat] Yet Eustratius treats Proclus as a positive source for articulating Aristotle, not just in a negative sense, again in a similar way to the cases where Proclus himself will use Aristotle positively when not disagreeing with Plato.[^procl-arist]

[^trizio-eust1]: See e.g. @trizio2016 122--142.
[^alex-plat]: ==‌[mention recent scholarship showing contrast of Aristotle harmonism/criticalism b/w 5th-cent. Athenians and 5th/6th-cent. Alexandrians]==
[^procl-arist]: @trizio2016 226; see also ==‌[scholarship pointing out Proclus' positive use of Arist.]==.

Other scholarship bearing on Eustratius' reliance on Proclus is more scattered, but consistent in scope: Giocarinis (1964) discusses Eustratius' doctrine of ideas in general terms, without engaging the *Republic* commentary specifically;[^giocarinis] Steel (2002) notes Eustratius's explicit references to Platonist exegeses---including a passage where Eustratius names Platonists debating the Good in connection with Plato's *Parmenides* (*In Eth.* 49.7--11)---but does not mention the implicit reference in *In Eth.* 87.9--12 to Proclus' *Republic Commentary*, as we discuss more below. Mercken (1990) (esp. 410--419), in his contribution to Sorabji's *Aristotle Transformed*, likewise notes Eustratius' dependence on Proclus in key parts of his *Commentary on Nicomachean Ethics*. Perczel's 2025 chapter and Gersh's contribution to Calma's second *Reading Proclus* volume each note further parallels to Proclus in Eustratius without addressing the *Republic* commentary as a source text.[^gershperczel] Trizio's earlier 2009 article, focused on Book VI of the *Ethics* commentary, establishes further general parallels but again does not extend to material drawn from Proclus's *In Rempublicam*.[^trizio2009]

Taken together, Eustratius' indebtedness to Proclus has been recognized in the scholarship, and his use of Proclus' *Republic Commentary* has been acknowledged. The full extent of this engagement---particularly the *Republic Commentary*, as we consider in our first case study (§6.1)---has not yet been detailed: in particular, the causal pairing of being and well-being, and the phrase anchoring the differentiation of lives to a daemonic hierarchy, discussed in §6 below, do not appear to figure in this literature.

[^giocarinis]: Giocarinis 1964.
[^mercken1990]: Mercken 1990, in Sorabji (ed.), *Aristotle Transformed*.
[^perczel2025]: Perczel 2025.
[^gersh2022]: Gersh 2022, in Calma (ed.), *Reading Proclus and the Book of Causes*, vol. 2, "Universals, Wholes, *Logoi*."
[^trizio2009]: Trizio 2009, "Neoplatonic Source-Material in Eustratios of Nicaea's Commentary on Book VI of the Nicomachean Ethics."


The general channel of Psellos' influence on Eustratius is likewise acknowledged in the scholarship, chiefly (again) by Trizio, whose 2016 monograph situates Eustratius within the wider absorption of Neoplatonic material that Psellos helped recirculate in eleventh-century Constantinople, and whose 2014 chapter on eleventh- and twelfth-century Byzantium traces the same Proclan revival through Psellos more broadly.[^trizio2016-psellos][^trizio2014] Psellos and Eustratius are also linked elsewhere in the scholarship on independent grounds---their shared engagement with the problem of universals has drawn some attention---but this connection concerns a different philosophical question and has not, so far as we have determined, been extended to the logical-theological material discussed in §6.2 below.[^universals]

What the existing literature has not registered is the specific transfer at issue in our second case study: the reproduction, in Eustratius' commentary on the *Posterior Analytics*, of the qualifying argumentative frame Psellos builds around Aristotle's rule of predication in his anti-Eunomian polemic in the *Theologica*. Neither Proclus nor Psellos appears in the indices nominum of the standard editions of Eustratius' logical commentaries, and we have found no discussion in the secondary literature --- including the studies just cited --- of this specific frame migrating from Psellos's theological polemic into Eustratius' treatment of Aristotelian logic, nor of its further recurrence in his *Ethics* commentary (§6.2). We treat this, provisionally, as previously unidentified.

[^trizio2016-psellos]: Trizio 2016.
[^trizio2014]: Trizio 2014.
[^universals]: [add citation(s) for the Psellos/Eustratius universals-nominalism connection, if you want to keep this sentence]


## 3. Corpus of Texts under Analysis

The pilot corpus comprises 29 works, totalling 2,371,796 words as recorded in the corpus manifest (Table 1): 26 Byzantine texts spanning the seventh to twelfth centuries and three ancient control texts. For the Byzantine texts, we select the seventh--twelfth-century period insofar as this time saw the transition from an indirect engagement with ancient philosophical sources (e.g., implicit re-use of arguments and quotations or paraphrases from ancient philosophical sources, often in theological treatises) to an explicit engagement (esp. commentaries on Aristotle and Proclus), conditioned by a sudden concern with how Byzantines saw themselves in relation to the ancient philosophical tradition, either as a whole or in relation to specific parts of that tradition. The Byzantine material divides chronologically into a seventh--eighth-century layer (Stephanus of Alexandria, the *Doctrina Patrum*, Maximus the Confessor, John of Damascus), a ninth--tenth-century layer (Photius, Arethas of Caesarea), and an eleventh--twelfth-century layer that carries the analytical weight of the pilot: the commentaries of Eustratius of Nicaea---the target of both case studies---alongside Michael Psellos, Michael of Ephesus, and Nicholas of Methone. The three ancient controls (Plato, *Respublica*; Aristotle, *Ethica Nicomachea*; Proclus, *In Rempublicam*) were selected to cover the source traditions most heavily quarried by the Byzantine corpus: the Platonic and Aristotelian base texts of the commentary tradition, and the Neoplatonic exegesis whose covert afterlife Case Study A investigates.

| ID | Author | Work | Edition | Source | Words |
|---|---|---|---|---|---|
| **Ancient controls** | | | | | |
| tlg0059.tlg030 | Plato | *Respublica* | Burnet 1902 (OCT) | OGL (Perseus) | 88,543 |
| tlg0086.tlg010 | Aristotle | *Ethica Nicomachea* | Bywater 1894 (OCT) | OGL (Perseus) | 56,595 |
| tlg4036.tlg001 | Proclus | *In Platonis Rem publicam commentarii* | Kroll 1899--1901 (Teubner) | Scaife | 198,509 |
| **7th--8th c.** | | | | | |
| 9019.001 | Stephanus of Alexandria | *In De Interpretatione* | Hayduck 1885 (CAG 18.3) | TLG | 23,322 |
| 7051.001 | anon. | *Doctrina patrum de incarnatione verbi* | Diekamp 1981 | TLG | 53,846 |
| 2892.001 | Maximus the Confessor | *Quaestiones ad Thalassium* | Laga--Steel 1980--90 (CCSG) | TLG | 75,560 |
| 2892.044 | Maximus the Confessor | *Epistulae* | PG 91 | OCR (PG) | 89,771 |
| 2892.050 | Maximus the Confessor | *Ambigua ad Thomam* | Janssens 2002 (CCSG) | OCR | 8,158 |
| 2934.004 | John of Damascus | *Expositio fidei* | Kotter 1973 (PTS) | TLG | 57,349 |
| 2934.002 | John of Damascus | *Dialectica* | Kotter 1969 (PTS) | TLG | 20,618 |
| **9th--10th c.** | | | | | |
| 4040.001 | Photius | *Bibliotheca* | Henry 1959--77 / PG 101--104 | TLG | 324,266 |
| 2130.038 | Arethas of Caesarea | *Scholia in Porphyrii Isagogen* | Busse 1894 (CAG 4.1) | OCR (CAG) | 164,413 |
| 2130.039 | Arethas of Caesarea | *Scholia in Categorias* | Busse 1894 (CAG 4.1) | OCR (CAG) | 160,390 |
| **11th--12th c.** | | | | | |
| 4031.002 | Eustratius of Nicaea\* | *In Ethica Nicomachea I* | Heylbut 1892 (CAG 20) | TLG | 42,116 |
| 4031.003 | Eustratius of Nicaea\* | *In Ethica Nicomachea VI* | Heylbut 1892 (CAG 20) | TLG | 55,673 |
| 4031.001 | Eustratius of Nicaea\* | *In Analytica Posteriora II* | Heylbut 1907 (CAG 21.1) | TLG | 97,907 |
| 2702.012 | Michael Psellos\* | *Theologica I* | Gautier 1989 (Teubner) | TLG | 131,654 |
| 2702.010 | Michael Psellos | *Philosophica minora I* | O'Meara 1989 | TLG | 81,807 |
| 2702.011 | Michael Psellos | *Philosophica minora II* | O'Meara 1992 | TLG | 43,810 |
| 2702.028 | Michael Psellos | *De omnifaria doctrina* | PG 122 / Westerink 1948 | OCR (PG) | 62,838 |
| 4034.001 | Michael of Ephesus | *In EN IX--X* | Heylbut 1892 (CAG 20) | TLG | 59,144 |
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


## 4. FLAME: The Matching Engine

Text reuse is detected by FLAME (Fuzzy Levenshtein-tolerant Ancient Matching Engine), an n-gram chain aligner developed for morphologically rich historical languages and adapted from a sister project. FLAME performs an exhaustive all-pairs sweep: every comparison unit of every work is matched against every unit of every other work.

**Segmentation.** Each work is first stripped of three classes of non-authorial material: modern editorial metadata (CTS URNs, EpiDoc markup, Creative Commons licence strings, removed by pattern matching); critical-apparatus sigla (*om.*, *ss*, *m1* and similar, removed conservatively---only notations followed by a period or space delimiter---to avoid deleting genuine Greek or Latin words); and generic scholastic transition formulas (τοῦτο δὲ ταὐτόν ἐστι τῷ, ἐν δὲ τῇ λέξει, τὰ ἑξῆς), which are the structural furniture of line-by-line commentary rather than authorial content. The cleaned text is segmented into sliding windows of 140 words with a 25-word overlap, aligned where possible to sentence boundaries (Greek period ·, question mark ;, and the line conventions of the editions). The window size is a compromise: large enough to contain a complete argumentative period, small enough to keep accidental collocations from accumulating. No orthographic normalisation is applied beyond the Unicode standardisation of the source texts, and no lemmatization is performed; the comparison operates on surface forms throughout.

**Phase 1---Tokenization.** Each unit is decomposed into character-level n-grams of length 4 (quadrigrams), and a hash is computed for each. Quadrigrams were chosen as the balance point: trigrams flood the candidate space of a highly formulaic language, while pentagrams begin to miss orthographically variant repetitions.

**Phase 2---Candidate retrieval.** N-gram hash collisions between two units are clustered. Clusters below the `max_candidates` ceiling (default 4,000) pass to alignment; denser clusters indicate high-similarity unit pairs and are prioritised.

**Phase 3---Chain alignment.** Within each cluster, character-level Levenshtein similarity is computed, and consecutive n-grams whose similarity meets the `fuzz_threshold` (default 0.75, i.e. at least 75% character overlap) are merged into chains. A chain thus represents a run of consecutively matching *words*, not raw character n-grams; chains shorter than `min_chain_words` (default 2) are discarded. Each n-gram tolerates at most one mismatched character, which is what absorbs the systematic orthographic variance of Byzantine transmission---itacism (η/ι/ει/οι), αι/ε confusion, movable ν, diacritic loss in OCR---without lemmatization or normalisation.

FLAME deliberately excludes gapped (non-adjacent) alignment: every element of a chain must be consecutive in both source and target. This prioritises precision over recall. It will miss paraphrastic reuse and reordered argument, but in a corpus dominated by commentary---where syntactic reordering is a routine rewriting strategy---admitting gaps multiplies false positives from commentary-specific syntax faster than it recovers genuine reuse.

For each match, FLAME records the work identifiers, citation-page references, a normalised similarity score, the chain length in words, the total matched tokens, the token range of the match within each citation-page unit, the matched snippets, and the chronological era of each side. Output is written to NDJSON and flat TSV. The Match IDs cited in §6 are the 1-based positions of their records in `text_reuse_matches.ndjson`, by which they are reproducibly recoverable from the released archive. On the 29-work corpus, the sweep evaluated 406 work pairs in approximately 140 minutes on a standard workstation without GPU acceleration, and produced **35,753 raw matches**. All numerical claims in this paper are computed from this raw set by a single script (`compute_reported_numbers.py`), released with the archive together with its output (`reported_numbers.json`), which records input hashes and run date.


## 5. The Filtering Architecture

Raw string matching over a tradition this formulaic is dominated by philologically inert matches. The filtering architecture separates the two phenomena of interest---Byzantine reception of ancient sources, and covert inter-Byzantine borrowing---and removes, in a controlled and quantified way, everything else.

### 5.1 Partition of the raw match set

The 35,753 raw matches partition into three disjoint classes by the author identity of the two sides:

| Class | Definition | Matches |
|---|---|---|
| BYZ–ANC | Byzantine work × ancient control | 6,426 |
| BYZ–BYZ (same author) | Different works by one Byzantine author | 6,273 |
| BYZ–BYZ (different author) | Two distinct Byzantine authors | 23,054 |

Same-author matches are excluded from inter-author analysis by definition (an author repeating himself is not borrowing). The BYZ–ANC set is the raw material of the reception analysis; the different-author BYZ–BYZ set holds the candidates for inter-Byzantine borrowing.

### 5.2 The Topos Exclusion Matrix

The dominant source of false positives among the BYZ–BYZ candidates is the shared-ancient-source effect: two Byzantine authors who both quote *Categories* 1b10 produce a string match between each other that is in fact two independent citations of Aristotle. The pilot's diagnostic case was Stephanus of Alexandria (7th c.) and Eustratius (12th c.), who share the clause γὰρ πᾶς οὐ τὸ καθόλου σημαίνει ἀλλ' ὅτι καθόλου---verbatim *De Interpretatione* 17b12, not a Byzantine transfer.

The Topos Exclusion Matrix filters these cases using the control corpus, in four steps. First, FLAME is run between every Byzantine work and the three ancient controls, producing the BYZ–ANC match set (6,426 matches). Second, for each Byzantine work, the citation-page coordinates of all its BYZ–ANC matches are collected---the "hot coordinates," regions of the Byzantine text known to overlap ancient source material. Third, every BYZ–BYZ match is tested against these coordinates: if either Byzantine side's token range overlaps a hot coordinate on the same citation page, with overlap ratio at least `min_ratio` (default 0.50) of the match's own length, the match is tagged `ancient_commonplace`. Formally, a BYZ–BYZ match *M* whose Byzantine side *B* occupies token range *w_B* on citation page *p_B* is tagged iff there exists a control coordinate *c* on *p_B* with |*w_B* ∩ *c*| / |*w_B*| ≥ 0.50.

Applied to the full BYZ–BYZ set (29,327 matches), the filter tagged **11,487 matches (39.2%)** as ancient commonplaces, leaving a clean BYZ–BYZ remainder of 17,840. That over a third of raw string identity between Byzantine authors dissolves into shared reliance on three ancient works is itself a finding: it quantifies, for the first time on this corpus, how much of the apparent inter-Byzantine textual network is an artifact of common sources.

One design point requires explicit statement. Proclus's *In Rempublicam* plays a dual role: as a control text it supplies hot coordinates for the BYZ–BYZ filter, while Proclus–Byzantine matches are simultaneously the primary signal of the reception analysis (and of Case Study A). This is deliberate, not circular, because the two uses answer different questions. The filter asks whether a given Byzantine–Byzantine string match is explained by common ancient material; the reception analysis asks how Byzantine authors engage the ancient inheritance. A Proclus passage quoted independently by two Byzantines is a false positive for the first question and evidence for the second.

### 5.3 Work-package thresholds

The clean material then passes through thresholds calibrated per research strand. The BYZ–ANC matches feed the reception analysis in three chronological layers, at chain length ≥ 6 with a score floor of 0.001 for the seventh–tenth-century layers, and at the stricter chain ≥ 8 with score ≥ 0.01 for the eleventh–twelfth-century layer, whose lemma-dense commentaries generate proportionally more noise. This yields 7, 14, and 678 reception candidates respectively. The clean different-author BYZ–BYZ matches pass a chain ≥ 6 threshold---motivated by the chain-length distribution of the raw set, in which 86.3% of different-author matches fall below chain 6 and are overwhelmingly coincidental short-gram overlap---yielding the intra-Byzantine candidate set, to which a further 877 `ancient_commonplace`-tagged matches are deliberately restored (below), for an intra-Byzantine total of 4,561 and a pipeline total of **5,260 candidate matches**.

### 5.4 Retained commonplaces: why exclusion cannot be absolute

The 877 restored matches embody the architecture's most important refinement. "Commonplace" and "genuine reuse" are not disjoint categories: a Byzantine author can adopt an ancient lemma *and* wrap it in a distinctive syntactic or polemical frame which a later author then reproduces. In such a case the ancient core is common property---both authors could cite it independently---but the frame is a genuine vector of transfer, and a filter that discards the match on the strength of the core alone throws away the signal with the noise. Case Study B is the configuration this filter cannot settle on its own. The shared string is Aristotle's predication rule---a common ancient lemma---yet the Topos Exclusion Matrix does not tag the Psellos--Eustratius alignment at *In APo* II /82#3 as a commonplace: it passes the filter untagged and survives as a clean candidate rather than a restored one (§6.2). The transferred object, Psellos's anti-Eunomian qualification of the rule, is precisely what string-level exclusion cannot see, which is why a filter built on the *ancient core* alone would discard the very signal at issue. The tagged matches that *are* restored to the intra-Byzantine candidate set are likewise presented to the philologist for contextual evaluation rather than silently discarded, and the planned bidirectional refinement of the filter---distinguishing matches where both sides merely hit the control from matches where one side reframes it---is a direct methodological outcome of the pilot.


## 6. Results

The clean candidate set produced by the filtering architecture (§5) is still too large to argue from individually. What follows is not a survey of that set but two controlled comparisons, presented at three levels of confidence: matches confirmed by close reading as genuine textual dependence; a single, richly corroborated case of structural transfer; and candidate matches whose status remains genuinely open, retained here precisely because the filtering architecture is designed to reveal such cases for philological (as well as philosophical) adjudication, beyond the algorithm's threshold (§5.4).

### 6.1 Case Study A: Proclus in Eustratius' *Ethics* Commentary

Comparing Proclus' *In Rempublicam* against Eustratius' *In Ethica Nicomachea I* yielded 94 raw matches, of which 5 survive as cross-author candidates after the Topos Exclusion Matrix removes shared-Aristotelian-source overlap. The residual ancient-commonplace rate for this pair---12%, against a corpus-wide rate of 39.2% (§5.2)---is itself notable: it indicates that whatever Eustratius is doing with Proclus, he is not merely repeating material both authors independently draw from Aristotle or Plato. The five matches, however, do not carry equal evidential weight.

**Matches 1--2: The distinction between being/well-being (confirmed)**

*Match 1:*
Proclus, *In Rempublicam* 101r#72 (= I, 207, lines 25--27 [Kroll 1899]):
> μιᾶς οὐσίας εἴτε ταὐτὸν εἴη τοῦ τε εἶναι αἴτιον\
> καὶ τοῦ εὖ εἶναι τοῖς οὖσιν... γὰρ **τὸ εἶναι δίδωσι**\
> **τοιοῦτον δώσει καὶ τὸ εὖ εἶναι**

Eustratius, *In EN I*, /87#1 (= 87, l. 9--12 [Heylbut 1892]):
> σπουδαστέον ἵν' ἡμῖν πρὸς τῷ εἶναι καὶ τὸ εὖ\
> εἶναι γένηται... καὶ μὴ τοῦ εὖ στερούμενοι ἀθλίως\
> ἔχωμεν τῆς ζωῆς· **εἰ δὲ θεὸς ὁ διδούς ἐστιν, εὔχεσθαι**\
> **δεῖ... ὡς ἂν ὁ τὸ εἶναι δοὺς καὶ τὸ εὖ εἶναι χαρίσηται**

*Match 2:*
Proclus, *In Rempublicam* 121v#138 (= I, 271, l. 1--2 [Kroll 1899]):
> ἄτοπον· οὐ γὰρ ταὐτὸν τὸ εἶναι καὶ τὸ εὖ εἶναι·\
> εἰ δὲ ἕτερόν τι τῆς οὐσίας...

Eustratius, *In EN I*, /87#1 (= 87, l. 9--10 [Heylbut 1892]) *‌[same passage as above]*:
> ἔστι καὶ σπουδαστέον ἵν' ἡμῖν πρὸς τῷ εἶναι καὶ\
> τὸ εὖ εἶναι γένηται...

In Match 1, particularly in the bolded parallel, we see a general parallel: in speaking about the distinction between being (εἶναι) and well-being (εὖ εἶναι), both Eustratius and Proclus also assert that the cause of being also gives well-being. Similarly, Match 2 shows another, nearby passage in Proclus, while pointing to the same Eustratius passage, where Proclus asserts that being and well-being are not the same---fitting also with Eustratius' (as well as Proclus' earlier) claim that the giver of being may also provide a distinct character besides being---i.e. well-being.

Eustratius' commentary covers Aristotle's text at *Nicomachean Ethics* 1099b--1100a, which merely gives the causes of happiness (nature, learning, habituation, or divine gift, treated as alternatives), not going into a metaphysical discussion of well-being as generated from being as such, which Eustratius' text---and certainly Proclus'---otherwise does. The language of being as a cause goes back to Proclus, and, as established in §2b, this specific phrasing in Eustratius is not identified in Trizio's discussions of Eustratius' dependency on Proclus. It does, nevertheless, corroborate their general thesis with a previously unremarked textual instance.

**Match 3: The differentiation of lives (qualified match)**

Proclus, *In Rempublicam* 18r#11 (= II, 104, l. 23--24 [Kroll 1901]):
> σύνταξιν ἔχουσι πρὸς αὐτὰς κατὰ τὰς\
> τῶν βίων διαφοράς...

Eustratius, *In EN I*, /34#1 (= 34, l. 4--5 [Heylbut 1892]):
> οἱ ἄνθρωποι περὶ εὐδαιμονίας κατὰ τὰς τῶν βίων\
> διαφορὰς καὶ τῶν προαιρέσεων...

The underlying topos---the tripartite division of lives (pleasure, politics, contemplation)---goes back to Aristotle (*EN* 1095b17--19). In itself, this tells us nothing unique just in relation to Proclus: both authors, one could object, merely discuss the same common notion. However, what reveals the unique Proclean influence in Eustratius' usage is that the phrase does not describe Aristotle's own tripartition; it is Proclus' device for anchoring a daemonic hierarchy onto the lives, an application Aristotle does not make and Eustratius' immediate context does not obviously require. As with Matches 1--2, this specific pairing is absent from the existing scholarship on Eustratius' use of Proclus (§2b).

**Match 4: Virtue and activity (unresolved match)**

Proclus, *In Rempublicam* 4v#2:
> ταῖς δὲ μερικαῖς αἱ σχέσεις αὗται, καὶ αἱ κατ'\
> αὐτὰς προσήκουσι κινήσεις...

Eustratius, *In EN I* /96#2 (ad *EN* 1100b22--1101a8):
> αἱ δ' ἀρεταὶ καὶ αἱ κατ' αὐτὰς ἐνέργειαι\
> βεβαιόταται πάντων τῶν ἀνθρωπίνων εἰσίν

==[precise Kroll/Heylbut line references still needed for this match]==

The shared span is the three-word correlative αἱ κατ' αὐτὰς, embedded in a generic X δέ Y, καὶ αἱ κατ' αὐτὰς Z construction. This correlative pattern is a feature of philosophical Greek prose generally rather than a Proclus-specific fingerprint; the same shape would plausibly turn up between any two authors discussing a subject and its corresponding attributes or activities. We do not regard this as established transmission. It is retained here, rather than silently dropped, in keeping with the filtering architecture's principle (§5.4) of surfacing short shared frames around a commonly treated topic for philological review rather than settling their status automatically.

**Match 5: The "nothing other than" formula (candidate, unresolved)**

Proclus, *In Rempublicam* 196v#14:
> τοῖς αὐτοῖς φησίν ἥδεσθαι καὶ λυπεῖσθαι·\
> τοῦτο δὲ οὐδὲν ἄλλο ἐστὶν ἢ τὸ τὰ αὐτὰ νομίζειν\
> ἀγαθὰ καὶ κακά

Eustratius, *In EN I* /90#3 (ad *EN* 1099a7--21):
> τοῦτο δ' οὐδὲν ἄλλο ἐστὶν ἢ τὸ εἶναι αὐτοὺς\
> σπουδαίους...

==[precise Kroll/Heylbut line references still needed for this match]==

τοῦτο δὲ οὐδὲν ἄλλο ἐστὶν ἢ ("this is nothing other than...") is a stock definitional formula across the Aristotelian commentary tradition generally, used by commentators over centuries to introduce a restatement or identification. Its recurrence here is not, on its own, evidence of a Proclus-specific channel; the risk of independent, coincidental use is high given how mechanically this formula recurs in scholastic Greek prose. We flag this candidate for the segmentation step directly: the phrase is a plausible addition to the list of generic transition formulas already stripped in preprocessing (§4), and its survival as a match here may be an artifact of that list's incompleteness rather than a genuine transmission signal. We do not include Match 5 as evidence for our argument in what follows, and note it as a diagnostic case for refining the exclusion list.

### 6.2 Case Study B: Psellos's Anti-Eunomian Frame in Eustratius' Logic --- and Beyond

The second case study concerns a single cluster of matches between Michael Psellos' *Theologica I* and Eustratius' *In Analytica Posteriora II*, anchored on Match ID 28636 (chain length 6; score 0.0444). Its evidential structure differs from Case Study A in an important way: the shared string is a commonplace phrase by design---namely, Aristotle's predicational rule from *Categories* 1b10: "Whatever is said to be according to something, these things will also spoken according to the subject" (κατά τινος λέγεται, ταῦτα καὶ κατὰ τοῦ ὑποκειμένου ῥηθήσεται)---and one the Topos Exclusion Matrix might be expected to catch. In the run reported here it is not caught: the match survives untagged as a clean intra-Byzantine candidate rather than a restored commonplace (§5.4), a fact that already shows the exclusion logic cannot operate on the string alone. What the match set nonetheless captures is not the quotation but rather the syntactic *frame* Psellos builds around it:

Psellos, *Theologica I* (%3/#4), anti-Eunomian polemic:
> οὐ γὰρ ἁπλῶς «ὅσα κατά τινος λέγεται, καὶ κατὰ\
> τοῦ ὑποκειμένου τούτῳ ῥηθήσεται», ἀλλὰ δῆλον κατὰ\
> τίνος καὶ τίνα. Πῶς μὲν οὖν παρελογίσατο ὁ Εὐνόμιος,\
> καὶ τίνι εἴδει τῶν σοφισμάτων χρησάμενος τὸν παραλογισμὸν\
> ἐποιήσατο, προϊόντες ἐροῦμεν... Ἀκηκοὼς ὁ Ἀνόμοιος τοῦ\
> Ἀριστοτέλους ἐν Κατηγορίαις εἰρηκότος ὅτι «ὅσα κατά τινος\
> λέγεται, ταῦτα καὶ κατὰ τοῦ ὑποκειμένου τούτῳ ῥηθήσεται»,\
> ἀβασανίστως τὸν λόγον ἐδέξατο...

Eustratius, *In Analytica Posteriora II* (/82#3), logical commentary:
> ...ὑποκειμένου λεγομένων, «ὅσα κατὰ τοῦ κατηγορουμένου\
> λέγεται, ταῦτα καὶ κατὰ τοῦ ὑποκειμένου ῥηθήσεται»,\
> ἀλλὰ τοῦ μὲν ζῴου ἐν...

==[edition/page reference for Psellos, Theologica I %3/#4, per Gautier 1989, still needed]==

The shared core is Aristotle's rule of predication, familiar and unremarkable on its own. What makes the match significant is what both authors do with it. Psellos embeds the rule within a commentary on the Christian patristic response against Eunomius of Cyzicus, the fourth-century Anomoean theologian who, Psellos and his patristic sources claim, used the rule fallaciously to deny the Son's consubstantiality. Eustratius, writing a formal commentary on the *Posterior Analytics* a century after Psellos' time, with no reference to the Eunomian controversy, or (let alone) Psellos' commentary, reproduces the same qualifying phrasing: οὐ γὰρ ἁπλῶς... ἀλλὰ δῆλον ("for not only ... but it is clear [etc]"), with which Psellos qualifies the predication rule before turning to Eunomius. In the same way, Eustratius provides the same Aristotle quote, and then qualifying "but of animal, they are properties in the 'what it is', simply, whereas of man ...[etc]" (lines 31--32: ἀλλὰ τοῦ μὲν ζῴου ἐν τῷ τί ἐστιν ἴδια ἁπλῶς [etc])---suggesting a similar formulation, between speaking of something 'simply' while qualifying (οὐ γὰρ ἁπλῶς... ἀλλὰ δῆλον). As established in §2b, neither Proclus nor Psellos appears in the index nominum of the standard editions of Eustratius' commentaries, and the parallel has, so far as we have determined, gone unremarked in the philological literature to date.

Three further considerations strengthen the case beyond what a single match could support:

- **Recurrence at the same target locus, independent Psellos phrasings**: IDs 28637 (*Theologica I* 3/#1) and 28638 (*Theologica I* 3/#5, the variant hedge οὐ τοίνυν ὅσα κατά τινος...) join the anchor in aligning on the same Eustratius locus (*In APo* II /82#3), all at chain 6 but drawn from distinct formulations of the predication rule. The qualifying move is thus a stable feature of how Eustratius handles this material, not a single verbal accident.
- **Sub-threshold alignments in the *Ethics* commentary, not claimed as evidence**: the raw sweep also surfaces short Psellos--Eustratius alignments in *In EN VI* that fall below the pipeline's chain ≥ 6 reporting threshold---IDs 28815 (*Theologica I* 3/#10 × *In EN VI* /268#2, chain 4) and 28824 (*Theologica I* 24/#2 × *In EN VI* /356#2, chain 4)---and are accordingly absent from the candidate set of §5.3. On the aligned strings they do not reproduce the predication-rule frame treated above: the former aligns on a passage concerning being and non-being (τὸ μὴ ὂν δοξαστόν), the latter on the ἢ εἴδει ἢ γένει differentia. We therefore do not count them as evidence that the Psellan framework migrates into the ethical work; whether anything beyond the anchor locus is at stake is left open for philological adjudication on the full text.
- **Absence from the tradition's paratextual record**: because this transfer is unmarked by citation in either the manuscript tradition, so far as the standard editions record, or in modern scholarship, it exemplifies precisely the covert borrowing this paper sets out to detect---the category of transmission that citation-based tools such as BIBLINDEX cannot reach by design (§2a).

We treat this cluster as the paper's central positive result: a case where the pipeline's chain-length and repeated-locus evidence together support a claim that would be difficult to establish and harder to notice by manual reading alone.

## 7. Discussion and Conclusion

As briefly mentioned above, the results of Cases A--B provide us promise, especially in Case A's Matches 1--2 and (with qualification) 3, which determinately show a direct reference to Proclus' *Republic Commentary*; and with Case B, although we find a syntactic match between Psellos and Eustratius, the framing confirms Psellos' influence in Eustratius' way of presenting Aristotle, and thus Psellos' broader authority, at least in terms of discussing Aristotelian logic. [...]

Three limits bound the pipeline's claims. Direction is supplied by chronology and context, never by the string evidence itself, so a common lost source or an intermediary---a florilegium of the kind whose transmission logic SAWS documented---can only be excluded by targeted controls, not by the cascade; the case studies accordingly specify collocational tests against the intervening commentary tradition and, for Case B, the Cappadocian anti-Eunomian corpus. Surface-form comparison under-detects inflectional variation and paraphrase (Moritz et al., 2016; Manjavacas et al., 2019). And every one of the 5,260 candidates is computational output, not a philological result: the pipeline's function is to reduce thirty-five thousand raw matches to a set small and clean enough to be read---which is where the philology begins.

\<!-- what does mediated, unmarked transmission of this kind tell us about Eustratius' method of composition, and about "authority" as a category in twelfth-century philosophical writing—does citing without naming一reflect assumed common knowledge, a rhetorical strategy, or something else. This is where the paper earns its place as more than a tool demo, and it's pure historian-of-philosophy territory. -->


\<!-- pilot validates the pipeline for scaling to the full ByzAntiq corpus; state concretely what expands (more authors, more centuries, refinement of the exclusion list per the Match 5 issue) -->

\<!-- reserve for conclusion: The pilot corpus spans the seventh to twelfth centuries because this window brackets a broader shift in how Byzantine philosophers positioned themselves with respect to ancient authorities — from largely unmarked absorption in the earlier centuries toward the more self-conscious, at times contested, engagement visible by the twelfth. Mapping implicit alongside explicit citation across this range is accordingly suited to tracing that shift directly; the method itself, however, is not bound to this period, and could be extended in either direction as the corpus warrants. -->


## 8. References

==‌[insert others]==

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


<!-- general sect's:\

2. Related work — two strands, not one
2a. Computational text reuse tools (colleague, primarily) — TRACER, Passim, Tesserae, BIBLINDEX, SAWS, as already drafted.
2b. Existing scholarship on Eustratius's sources (you, and this section doesn't exist yet) — Trizio 2016, Steel 2002, Ierodiakonou, Giocarinis 1964, the general Psellos-Proclus-Eustratius line. This section is where you state plainly what's already known, so that §6 can state plainly what's new. Skipping this is the single biggest risk to the paper's credibility — a reviewer who knows Trizio's monograph will ask why it isn't cited.
2c. Survivability of results (unwritten)
3. Corpus (colleague) — as drafted.
4. FLAME: the matching engine (colleague, with your input on the tokenization-language fix).
5. The filtering architecture (colleague) — Topos Exclusion Matrix, thresholds, as drafted.
6. Results: two case studies (joint, but the interpretive weight is yours) — the draft I gave you. The tool supplies candidates, chain lengths, scores; you supply the argument for why a match is or isn't doing Proclus-specific or Psellos-specific work rather than repeating a commonplace. This is not "confirming the computer's findings" — it's the actual philological argument the paper rests on, and it needs to explicitly engage §2b: for matches 1--3, say whether Trizio or Steel already discuss this passage, and if not, why it strengthens their general thesis; for Case B, state the absence from the indices nominum as your own bibliographic finding, checked, not asserted.
7. Discussion (you, primarily) — what does mediated, unmarked transmission of this kind tell us about Eustratius's method of composition, and about "authority" as a category in twelfth-century philosophical writing — does citing without naming一 reflect assumed common knowledge, a rhetorical strategy, or something else. This is where the paper earns its place as more than a tool demo, and it's pure historian-of-philosophy territory.
8. Conclusion/Outlook (you) — pilot validates the pipeline for scaling to the full ByzAntiq corpus; state concretely what expands (more authors, more centuries, refinement of the exclusion list per the Match 5 issue).

-->
