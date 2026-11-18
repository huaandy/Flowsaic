"""Degree map parsing from a www.saumag.edu-style program page. Fake HTML, no network or DB."""

from app.catalog.degree_maps import (
    parse_gen_ed,
    parse_program_page,
    program_slugs,
    trim_gen_ed,
    trim_page,
)

# Shaped like www.saumag.edu/academics/general-education/ (a shorter, made-up core).
GEN_ED_PAGE = """<html><body><div class="entry-content">
<h3>The Purpose</h3><p>Learning goals.</p>
<h2><span>The General Education Curriculum</span></h2>
<p>All degree-seeking students shall complete a minimum of 26 semester hours.</p>
<h3>English (6 hours)</h3>
<p>Fulfilled by completing the following two courses:</p>
<ul><li>ENGL 1113 Composition I</li><li>ENGL 1123 Composition II</li></ul>
<h3>Mathematics (3&#8211;5 hours)</h3>
<p>Fulfilled by completing one of the following courses:</p>
<ul><li>MATH 1023 College Algebra</li><li>MATH 1525 Calculus I</li></ul>
<h3>Science (8 hours)</h3>
<p><strong>Biological Science choice (4 hours)</strong>, one lecture and lab combination (see note 1):</p>
<ul><li>BIOL 1043 Introduction to Biology and BIOL 1041 Lab</li></ul>
<p><strong>Physical Science choice (4 hours)</strong>, one lecture and lab combination:</p>
<ul><li>PHYS 2003 College Physics I and PHYS 2001 Lab</li><li>GEOL 1003 Physical Geology and GEOL 1001 Lab</li></ul>
<h3>Social Science (9 hours)</h3>
<p><strong>Social Science choice (9 hours)</strong>, three of:</p>
<ul><li>PSYC 2003 General Psychology</li><li>3 hours of Foreign Language: SPAN 1053 or 1063 Elementary Spanish</li></ul>
<h3>Notes</h3>
<ol><li>Engineering majors may substitute.</li></ol>
<p>For the full requirements, see the catalog.</p>
</div></body></html>"""

PAGE = """<html><head>
<meta property="og:title" content="Imaginary Zoology | Academics | Southern Arkansas University">
</head><body>
<a href="https://catalog.saumag.edu/preview_program.php?catoid=10&#038;poid=9001&#038;returnto=370"
   class="prog-facts-value prog-facts-plan-link">2026-2027 <i></i></a>
<section class="prog-section" id="prog-curriculum"><div class="prog-curriculum-content">
<h4>University Requirement (2 hours)</h4>
<p>GSTD 1002 &#8211; Freshman Seminar</p>
<h4>General Education (28 hours)</h4>
<p><strong>Note</strong>: 7 hours of science are included in the major.</p>
<h4>Zoology (30 hours)</h4>
<p>ZOO 2103 &#8211; Zoology I and ZOO 2101 &#8211; Zoology I Lab<br />
ZOO 3103 &#8211; Imaginary Animals<br />
12 hours of upper-level Zoology electives</p>
<h4>Mathematics (8 hours)</h4>
<p>MATH 2033 &#8211; Discrete Mathematics</p>
<h4>Select 5 hours from the following:</h4>
<p>MATH 1525 &#8211; Calculus I<br />
MATH 2125 &#8211; Applied Calculus</p>
<h4>Select 3-5 hours from the following:</h4>
<p>MATH 1545 &#8211; Calculus II<br />
MATH 4233 &#8211; Data Science</p>
<h4>Physics (4 hours)</h4>
<p><strong>Select one of the following course combinations:</strong><br />
PHYS 2003 &#8211; College Physics I and PHYS 2001 &#8211; College Physics I Lab<br />
or<br />
PHYS 2203 &#8211; University Physics I and PHYS 2201 &#8211; University Physics I Lab</p>
<h4>Electives (3 hours)</h4>
<p>3 hours of unrestricted electives</p>
<h4>Total Hours &#8211; 120</h4>
</div></section>
<section class="prog-section" id="prog-minor"><div class="prog-curriculum-content">
<h4>Minor Requirements (9 hours)</h4>
<p>ZOO 2103 &#8211; Zoology I<br />ZOO 3103 &#8211; Imaginary Animals<br />ZOO 4103 &#8211; Dragons</p>
<h4>Total Hours &#8211; 9</h4>
</div></section>
<script>var tracking = 1;</script>
</body></html>"""

NAMES = {"9001": "Imaginary Zoology, BS", "9002": "Imaginary Zoology Minor"}


def groups_by_name(groups, found=None):
    found = {} if found is None else found
    for group in groups:
        found[group.name] = group
        groups_by_name(group.children, found)
    return found


def test_parse_major_tree():
    result = parse_program_page(PAGE, "imaginary-zoology", NAMES)
    assert result.skipped is None
    major = result.programs[0]
    assert (major.name, major.catalog_year, major.total_hours, major.poid) == (
        "Imaginary Zoology, BS", "2026-2027", 120, "9001",
    )
    assert [g.name for g in major.groups] == [
        "University Requirement (2 hours)", "General Education (28 hours)", "Zoology (30 hours)",
        "Mathematics (8 hours)", "Physics (4 hours)", "Electives (3 hours)",
    ]
    groups = groups_by_name(major.groups)

    zoology = groups["Zoology (30 hours)"]
    assert zoology.rule == "all"
    assert zoology.courses == ["ZOO 2103", "ZOO 2101", "ZOO 3103"]  # lecture + lab pair split
    assert zoology.note == "12 hours of upper-level Zoology electives"

    assert groups["General Education (28 hours)"].courses == []
    assert groups["General Education (28 hours)"].note == "7 hours of science are included in the major."

    math = groups["Mathematics (8 hours)"]
    assert math.courses == ["MATH 2033"]
    select_5, select_3_5 = math.children
    assert (select_5.rule, select_5.hours_required, select_5.courses) == (
        "choose_hours", 5, ["MATH 1525", "MATH 2125"],
    )
    assert select_3_5.hours_required == 3 and select_3_5.note == "3-5 hours."

    physics = groups["Physics (4 hours)"]
    assert (physics.rule, physics.hours_required) == ("choose_hours", 4)
    assert physics.note == "One of these combinations: PHYS 2003 + PHYS 2001 or PHYS 2203 + PHYS 2201."
    assert major.problems == [
        "curriculum: Physics (4 hours) is a choice of course combinations; loaded as choose hours"
    ]


def test_minor_is_its_own_plan():
    minor = parse_program_page(PAGE, "imaginary-zoology", NAMES).programs[1]
    assert (minor.name, minor.total_hours, minor.poid) == ("Imaginary Zoology Minor", 9, "9002")
    assert minor.groups[0].courses == ["ZOO 2103", "ZOO 3103", "ZOO 4103"]


def test_select_line_inside_a_block():
    page = PAGE.replace(
        "<h4>Electives (3 hours)</h4>\n<p>3 hours of unrestricted electives</p>",
        "<h4>Experiential Learning (3 hours)</h4>\n<p><strong>Select 3 hours from the following:</strong><br />"
        "ZOO 4452 &#8211; Internship<br />ZOO 4551 &#8211; Field Work</p>",
    )
    groups = groups_by_name(parse_program_page(page, "z", NAMES).programs[0].groups)
    block = groups["Experiential Learning (3 hours)"]
    assert (block.rule, block.hours_required, block.courses, block.note) == (
        "choose_hours", 3, ["ZOO 4452", "ZOO 4551"], None,
    )


def test_minor_name_uses_the_catalog_name_after_the_colon():
    names = {"9001": "Science: Imaginary Zoology, BS", "9002": "Imaginary Zoology Minor"}
    minor = parse_program_page(PAGE, "z", names).programs[1]
    assert (minor.name, minor.poid, minor.problems) == ("Imaginary Zoology Minor", "9002", [])


def test_name_falls_back_to_the_page_title_and_is_flagged():
    major = parse_program_page(PAGE, "imaginary-zoology", {}).programs[0]
    assert major.name == "Imaginary Zoology"
    assert any("not on the saved catalog list" in problem for problem in major.problems)


def test_pages_for_other_catalogs_or_without_a_link_are_skipped():
    graduate = PAGE.replace("catoid=10&", "catoid=11&")
    assert parse_program_page(graduate, "x", NAMES).skipped == "links to another catalog (catoid 11)"
    no_link = PAGE.replace('class="prog-facts-value prog-facts-plan-link"', 'class="other"')
    assert parse_program_page(no_link, "x", NAMES).skipped == "no catalog Degree Plan link"


def test_trimmed_copy_parses_the_same_and_drops_scripts():
    trimmed = trim_page(PAGE)
    assert "tracking" not in trimmed
    full = parse_program_page(PAGE, "z", NAMES)
    small = parse_program_page(trimmed, "z", NAMES)
    assert [(p.name, p.total_hours, p.problems) for p in full.programs] == [
        (p.name, p.total_hours, p.problems) for p in small.programs
    ]


def test_parse_gen_ed_core():
    gen_ed = parse_gen_ed(trim_gen_ed(GEN_ED_PAGE))
    assert [(a.name, a.rule, a.hours) for a in gen_ed.areas] == [
        ("English (6 hours)", "all", 6),
        ("Mathematics (3–5 hours)", "choose_hours", 3),
        ("Science (8 hours)", "all", 8),
        ("Social Science (9 hours)", "all", 9),
    ]
    english, math, science, social = gen_ed.areas
    assert english.courses == ["ENGL 1113", "ENGL 1123"]
    assert (math.hours_required, math.courses) == (3, ["MATH 1023", "MATH 1525"])
    biology, physical = science.children
    assert (biology.name, biology.rule, biology.hours_required) == ("Biological Science choice", "choose_hours", 4)
    assert biology.note == "One lecture and lab combination (see note 1): BIOL 1043 + BIOL 1041."
    assert physical.courses == ["PHYS 2003", "PHYS 2001", "GEOL 1003", "GEOL 1001"]
    # "SPAN 1053 or 1063" gives both courses.
    assert social.children[0].courses == ["PSYC 2003", "SPAN 1053", "SPAN 1063"]
    assert social.children[0].note == "Three of."
    assert gen_ed.notes == ["Engineering majors may substitute."]


def test_gen_ed_is_attached_minus_what_the_major_covers():
    # The program's note says math and physical science are in the major: 26 - 3 - 4 = 19.
    page = PAGE.replace("General Education (28 hours)", "General Education (19 hours)").replace(
        "7 hours of science are included in the major.",
        "7 hours of mathematics and physical science requirements are included in the major.",
    )
    gen_ed = parse_gen_ed(GEN_ED_PAGE)
    major = parse_program_page(page, "z", NAMES, gen_ed).programs[0]
    block = groups_by_name(major.groups)["General Education (19 hours)"]
    assert [a.name for a in block.children] == ["English (6 hours)", "Science (4 hours)", "Social Science (9 hours)"]
    assert [c.name for c in block.children[1].children] == ["Biological Science choice"]
    assert "Gen ed notes: (1) Engineering majors may substitute." in block.note
    assert not any("gen ed adds up" in p for p in major.problems)


def test_gen_ed_hours_that_do_not_add_up_are_flagged():
    gen_ed = parse_gen_ed(GEN_ED_PAGE)
    page = PAGE.replace("7 hours of science are included in the major.", "See your advisor.")
    major = parse_program_page(page, "z", NAMES, gen_ed).programs[0]  # says 28, note covers nothing
    assert "gen ed adds up to 26 hours but the program says 28" in major.problems


def gen_ed_block(note: str, hours: int):
    page = PAGE.replace("General Education (28 hours)", f"General Education ({hours} hours)").replace(
        "7 hours of science are included in the major.", note
    )
    major = parse_program_page(page, "z", NAMES, parse_gen_ed(GEN_ED_PAGE)).programs[0]
    return groups_by_name(major.groups)[f"General Education ({hours} hours)"], major.problems


def test_gen_ed_hours_covered_by_the_major_come_out_of_that_area():
    # 26 - 3 = 23: the social science choice needs 6 of its 9 hours.
    block, problems = gen_ed_block("3 hours of social science requirements are included in the major.", 23)
    social = block.children[-1]
    assert social.name == "Social Science (6 hours)"
    assert social.children[0].hours_required == 6
    assert "6 hours for this program" in social.children[0].note
    assert not any("gen ed" in p for p in problems)


def test_covered_hours_drop_the_choice_the_major_already_requires():
    # The major requires PHYS 2003, so its 4 science hours are the physical science choice.
    block, problems = gen_ed_block("4 hours of science requirements are included in the major.", 22)
    science = groups_by_name(block.children)["Science (4 hours)"]
    assert [c.name for c in science.children] == ["Biological Science choice"]
    assert not any("gen ed" in p for p in problems)


def test_each_area_gets_its_own_hours():
    # "3 hours of mathematics, and 4 hours of physical science": 26 - 3 - 4 = 19.
    note = "3 hours of mathematics, and 4 hours of physical science requirements are included in the major."
    block, problems = gen_ed_block(note, 19)
    assert [a.name for a in block.children] == ["English (6 hours)", "Science (4 hours)", "Social Science (9 hours)"]
    assert not any("gen ed" in p for p in problems)


def test_an_area_already_dropped_is_not_reported():
    # "natural science" drops all of Science, so "physical science" has nothing left to drop.
    block, problems = gen_ed_block(
        "8 hours of natural science and physical science requirements are included in the major.", 18
    )
    assert [a.name for a in block.children] == ["English (6 hours)", "Mathematics (3–5 hours)", "Social Science (9 hours)"]
    assert not any("gen ed" in p for p in problems)


def test_a_note_that_lists_its_own_areas_keeps_only_those():
    # Engineering pages: "English Composition (6 hours) Social Science (3 hours)".
    block, problems = gen_ed_block("English Composition (6 hours) ​Social Science (3 hours)", 9)
    assert [a.name for a in block.children] == ["English (6 hours)", "Social Science (3 hours)"]
    assert block.children[1].children[0].hours_required == 3
    assert not any("gen ed" in p for p in problems)


def test_minor_named_by_its_own_heading():
    page = PAGE.replace("<h4>Minor Requirements (9 hours)</h4>", "<h4>Dragon Minors for Zoology Majors (9 Hours)</h4>")
    names = {"9001": "Imaginary Zoology, BS", "9003": "Dragon Minor for Zoology Majors"}
    minor = parse_program_page(page, "z", names).programs[1]
    assert (minor.name, minor.poid, minor.problems) == ("Dragon Minor for Zoology Majors", "9003", [])

    page = PAGE.replace("<h4>Minor Requirements (9 hours)</h4>", "<h4>Minor in Dragons (9 hours)</h4>")
    names = {"9001": "Imaginary Zoology, BS", "9004": "Dragons Minor"}
    assert parse_program_page(page, "z", names).programs[1].name == "Dragons Minor"


def test_minor_name_from_the_part_before_the_dash_or_the_colon():
    names = {"9001": "Science: Zoology - Dragons, BS", "9002": "Zoology Minor"}
    assert parse_program_page(PAGE, "z", names).programs[1].name == "Zoology Minor"
    names = {"9001": "Zoology: Dragons, BS", "9002": "Zoology Minor"}
    assert parse_program_page(PAGE, "z", names).programs[1].name == "Zoology Minor"


def test_a_note_that_names_a_course_keeps_its_text():
    page = PAGE.replace(
        "<p><strong>Note</strong>: 7 hours of science are included in the major.</p>",
        "<p><strong>Note</strong>: 8 hours are in the major. ZOO 2073 &#8211; Zoo Economics is required.</p>",
    )
    major = parse_program_page(page, "z", NAMES).programs[0]
    block = groups_by_name(major.groups)["General Education (28 hours)"]
    assert block.note == "8 hours are in the major. ZOO 2073 – Zoo Economics is required."
    assert block.courses == ["ZOO 2073"]
    assert any("names ZOO 2073" in p for p in major.problems)


def test_program_slugs_from_sitemap():
    sitemap = """<urlset>
    <url><loc>https://www.saumag.edu/academics/degrees/</loc></url>
    <url><loc>https://www.saumag.edu/academics/program/computer-science/</loc></url>
    <url><loc>https://www.saumag.edu/academics/program/minor-in-dance-2/</loc></url>
    <url><loc>https://www.saumag.edu/academics/program/computer-science/</loc></url>
    </urlset>"""
    assert program_slugs(sitemap) == ["computer-science", "minor-in-dance-2"]
