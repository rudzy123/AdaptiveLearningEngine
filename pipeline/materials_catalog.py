"""Curated catalog of free, open educational PDF resources."""

from __future__ import annotations

from dataclasses import dataclass

from config import MIT_OCW_BASE, STANFORD_CS161_BASE


@dataclass(frozen=True)
class MaterialResource:
    """A single downloadable educational resource."""

    url: str
    topic: str  # math | physics | cs | problems
    filename: str
    title: str
    institution: str
    subtopic: str = ""


def _mit(path: str) -> str:
    return f"{MIT_OCW_BASE}{path}"


def _stanford(path: str) -> str:
    return f"{STANFORD_CS161_BASE}{path}"


# Curated high-quality open resources (MIT OCW + Stanford CS161).
MATERIALS_CATALOG: list[MaterialResource] = [
    # --- Math: Linear Algebra (MIT 18.06) ---
    MaterialResource(
        url=_mit(
            "/courses/18-06sc-linear-algebra-fall-2011/"
            "c501620f128ab205bc267770934d707a_MIT18_06SCF11_ZoomNotes.pdf"
        ),
        topic="math",
        filename="mit_18_06_linear_algebra_zoom_notes.pdf",
        title="ZoomNotes for Linear Algebra (Gilbert Strang)",
        institution="MIT OpenCourseWare",
        subtopic="linear_algebra",
    ),
    MaterialResource(
        url=_mit(
            "/courses/18-06-linear-algebra-spring-2010/"
            "4d876a9159e32543eb0d73b4d4382f4c_MIT18_06S10ZoomNotes.pdf"
        ),
        topic="math",
        filename="mit_18_06_spring2010_zoom_notes.pdf",
        title="Linear Algebra Zoom Notes (Spring 2010)",
        institution="MIT OpenCourseWare",
        subtopic="linear_algebra",
    ),
    # --- Physics: Classical Mechanics (MIT 8.01SC) ---
    MaterialResource(
        url=_mit(
            "/courses/8-01sc-classical-mechanics-fall-2016/"
            "mit8_01scs22_chapter1.pdf"
        ),
        topic="physics",
        filename="mit_8_01_mechanics_chapter01_introduction.pdf",
        title="Classical Mechanics Ch.1: Introduction",
        institution="MIT OpenCourseWare",
        subtopic="mechanics",
    ),
    MaterialResource(
        url=_mit(
            "/courses/8-01sc-classical-mechanics-fall-2016/"
            "mit8_01scs22_chapter7.pdf"
        ),
        topic="physics",
        filename="mit_8_01_mechanics_chapter07_newtons_laws.pdf",
        title="Classical Mechanics Ch.7: Newton's Laws",
        institution="MIT OpenCourseWare",
        subtopic="mechanics",
    ),
    MaterialResource(
        url=_mit(
            "/courses/8-01sc-classical-mechanics-fall-2016/"
            "mit8_01scs22_chapter13.pdf"
        ),
        topic="physics",
        filename="mit_8_01_mechanics_chapter13_energy.pdf",
        title="Classical Mechanics Ch.13: Energy and Work",
        institution="MIT OpenCourseWare",
        subtopic="mechanics",
    ),
    MaterialResource(
        url=_mit(
            "/courses/8-01sc-classical-mechanics-fall-2016/"
            "mit8_01scs22_chapter10.pdf"
        ),
        topic="physics",
        filename="mit_8_01_mechanics_chapter10_momentum.pdf",
        title="Classical Mechanics Ch.10: Momentum",
        institution="MIT OpenCourseWare",
        subtopic="mechanics",
    ),
    # --- Physics: Thermodynamics (MIT 5.60) ---
    MaterialResource(
        url=_mit(
            "/courses/5-60-thermodynamics-kinetics-spring-2008/"
            "bc172a632ae28798bdb0078177bcec9c_5_60_lecture1.pdf"
        ),
        topic="physics",
        filename="mit_5_60_thermodynamics_lecture01.pdf",
        title="Thermodynamics Lecture 1: State of a System",
        institution="MIT OpenCourseWare",
        subtopic="thermodynamics",
    ),
    MaterialResource(
        url=_mit(
            "/courses/5-60-thermodynamics-kinetics-spring-2008/"
            "0bcd290ff179f0be4f8530854ad2dcde_5_60_lecture7.pdf"
        ),
        topic="physics",
        filename="mit_5_60_thermodynamics_lecture07.pdf",
        title="Thermodynamics Lecture 7: Calorimetry",
        institution="MIT OpenCourseWare",
        subtopic="thermodynamics",
    ),
    MaterialResource(
        url=_mit(
            "/courses/5-60-thermodynamics-kinetics-spring-2008/"
            "52946f97fcb18850c32e9d4b8f6bab6a_5_60_lecture15.pdf"
        ),
        topic="physics",
        filename="mit_5_60_thermodynamics_lecture15.pdf",
        title="Thermodynamics Lecture 15: Chemical Equilibrium",
        institution="MIT OpenCourseWare",
        subtopic="thermodynamics",
    ),
    MaterialResource(
        url=_mit(
            "/courses/5-60-thermodynamics-kinetics-spring-2008/"
            "8b3da396348c4c9bb3929b4d0057205e_5_60_lecture19.pdf"
        ),
        topic="physics",
        filename="mit_5_60_thermodynamics_lecture19.pdf",
        title="Thermodynamics Lecture 19: Clausius-Clapeyron",
        institution="MIT OpenCourseWare",
        subtopic="thermodynamics",
    ),
    # --- CS: Algorithms (MIT 6.006) ---
    MaterialResource(
        url=_mit(
            "/courses/6-006-introduction-to-algorithms-fall-2011/"
            "c32185c7158955425455159a8455298b_MIT6_006F11_lec01.pdf"
        ),
        topic="cs",
        filename="mit_6_006_algorithms_lecture01.pdf",
        title="Introduction to Algorithms Lecture 1",
        institution="MIT OpenCourseWare",
        subtopic="algorithms",
    ),
    MaterialResource(
        url=_mit(
            "/courses/6-006-introduction-to-algorithms-fall-2011/"
            "6b9b20992d8c6a0f3f10a34ff7878aa9_MIT6_006F11_lec02.pdf"
        ),
        topic="cs",
        filename="mit_6_006_algorithms_lecture02.pdf",
        title="Introduction to Algorithms Lecture 2 (AVL Trees)",
        institution="MIT OpenCourseWare",
        subtopic="algorithms",
    ),
    MaterialResource(
        url=_mit(
            "/courses/6-006-introduction-to-algorithms-fall-2011/"
            "90a37c49b07b105ea7a027abc67eddc6_MIT6_006F11_lec03.pdf"
        ),
        topic="cs",
        filename="mit_6_006_algorithms_lecture03.pdf",
        title="Introduction to Algorithms Lecture 3 (Sorting)",
        institution="MIT OpenCourseWare",
        subtopic="algorithms",
    ),
    MaterialResource(
        url=_mit(
            "/courses/6-006-introduction-to-algorithms-fall-2011/"
            "8ebfeb1c645b10b3709919603e7d51be_MIT6_006F11_lec04.pdf"
        ),
        topic="cs",
        filename="mit_6_006_algorithms_lecture04.pdf",
        title="Introduction to Algorithms Lecture 4 (Hashing)",
        institution="MIT OpenCourseWare",
        subtopic="algorithms",
    ),
    MaterialResource(
        url=_mit(
            "/courses/6-006-introduction-to-algorithms-fall-2011/"
            "83cdd705cd418d10d9769b741e34a2b8_MIT6_006F11_lec06.pdf"
        ),
        topic="cs",
        filename="mit_6_006_algorithms_lecture06.pdf",
        title="Introduction to Algorithms Lecture 6 (BFS)",
        institution="MIT OpenCourseWare",
        subtopic="algorithms",
    ),
    MaterialResource(
        url=_mit(
            "/courses/6-006-introduction-to-algorithms-fall-2011/"
            "bf7d79105762bf79bbc0925438e1468a_MIT6_006F11_lec07.pdf"
        ),
        topic="cs",
        filename="mit_6_006_algorithms_lecture07.pdf",
        title="Introduction to Algorithms Lecture 7 (DFS)",
        institution="MIT OpenCourseWare",
        subtopic="algorithms",
    ),
    # --- CS: Stanford CS161 (supplement) ---
    MaterialResource(
        url=_stanford("/winter2024/assets/files/lecture1-notes.pdf"),
        topic="cs",
        filename="stanford_cs161_lecture01_notes.pdf",
        title="Stanford CS161 Lecture 1 Notes",
        institution="Stanford CS161",
        subtopic="algorithms",
    ),
    MaterialResource(
        url=_stanford("/winter2024/assets/files/lecture2-notes.pdf"),
        topic="cs",
        filename="stanford_cs161_lecture02_notes.pdf",
        title="Stanford CS161 Lecture 2 Notes",
        institution="Stanford CS161",
        subtopic="algorithms",
    ),
    MaterialResource(
        url=_stanford("/winter2024/assets/files/lecture3-notes.pdf"),
        topic="cs",
        filename="stanford_cs161_lecture03_notes.pdf",
        title="Stanford CS161 Lecture 3 Notes",
        institution="Stanford CS161",
        subtopic="algorithms",
    ),
    # --- Problems: MIT 18.06 problem sets ---
    MaterialResource(
        url=_mit(
            "/courses/18-06sc-linear-algebra-fall-2011/"
            "f511d20996159f321b6704f5b2070e04_MIT18_06SCF11_Ses1.1prob.pdf"
        ),
        topic="problems",
        filename="mit_18_06_problem_set_1_1.pdf",
        title="18.06 Problem Set 1.1",
        institution="MIT OpenCourseWare",
        subtopic="linear_algebra",
    ),
    MaterialResource(
        url=_mit(
            "/courses/18-06sc-linear-algebra-fall-2011/"
            "2a96d025346d8845829251cb918caddd_MIT18_06SCF11_Ses1.2prob.pdf"
        ),
        topic="problems",
        filename="mit_18_06_problem_set_1_2.pdf",
        title="18.06 Problem Set 1.2",
        institution="MIT OpenCourseWare",
        subtopic="linear_algebra",
    ),
    MaterialResource(
        url=_mit(
            "/courses/18-06sc-linear-algebra-fall-2011/"
            "8e9ccbcc13300a9bda7f24a684bd16b6_MIT18_06SCF11_Ses1.3prob.pdf"
        ),
        topic="problems",
        filename="mit_18_06_problem_set_1_3.pdf",
        title="18.06 Problem Set 1.3",
        institution="MIT OpenCourseWare",
        subtopic="linear_algebra",
    ),
    MaterialResource(
        url=_mit(
            "/courses/6-006-introduction-to-algorithms-fall-2011/"
            "dcc62658425ffabc1dc93e9940589a66_MIT6_006F11_ps1.pdf"
        ),
        topic="problems",
        filename="mit_6_006_problem_set_1.pdf",
        title="6.006 Problem Set 1",
        institution="MIT OpenCourseWare",
        subtopic="algorithms",
    ),
    MaterialResource(
        url=_mit(
            "/courses/6-006-introduction-to-algorithms-fall-2011/"
            "e19680b53184ce34c80a665a25efc570_MIT6_006F11_ps2.pdf"
        ),
        topic="problems",
        filename="mit_6_006_problem_set_2.pdf",
        title="6.006 Problem Set 2",
        institution="MIT OpenCourseWare",
        subtopic="algorithms",
    ),
]
