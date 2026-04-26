"""
Management command: seed_data
Generates 10 Philippine schools with principals, students, activities, and leadership awards.

Usage:
    docker-compose exec web python manage.py seed_data
    docker-compose exec web python manage.py seed_data --flush   (clear first)
"""

import random
import urllib.request
from datetime import date, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from ldp_core.models import Activity, LeadershipAward, Person, School, User

# ─────────────────────────────────────────────────────────────────────────────
# Lookup tables
# ─────────────────────────────────────────────────────────────────────────────

MALE_FIRST = [
    "Ricardo", "Jose", "Miguel", "Carlos", "Eduardo",
    "Roberto", "Andres", "Danilo", "Renato", "Virgilio",
    "Ernesto", "Rodrigo", "Benjamin", "Alfredo", "Manuel",
    "Fernando", "Romulo", "Carlito", "Bienvenido", "Nicanor",
]
FEMALE_FIRST = [
    "Maria", "Ana", "Rosa", "Luz", "Cristina",
    "Gloria", "Elena", "Marites", "Rowena", "Melody",
    "Ligaya", "Cheryl", "Grace", "Michelle", "Joanne",
    "Geraldine", "Rosario", "Lourdes", "Divina", "Natividad",
]
LAST_NAMES = [
    "Santos", "Reyes", "Cruz", "Bautista", "Ocampo",
    "Garcia", "Mendoza", "Torres", "Castillo", "Villanueva",
    "Fernandez", "Gonzales", "Ramos", "Aquino", "Tolentino",
    "Flores", "Pascual", "Dela Cruz", "Delos Santos", "Adriano",
    "Buenaventura", "Camacho", "Dizon", "Espiritu", "Francisco",
    "Guerrero", "Herrera", "Isidro", "Jimenez", "Lacson",
]
COURSES_STUDENT = [
    "Grade 11 – STEM", "Grade 11 – ABM", "Grade 11 – HUMSS",
    "Grade 12 – STEM", "Grade 12 – ABM", "Grade 12 – GAS",
    "Grade 10 – Science", "Grade 9 – Technology",
]
COURSES_COLLEGE = [
    "Bachelor of Science in Information Technology",
    "Bachelor of Science in Nursing",
    "Bachelor of Science in Education",
    "Bachelor of Science in Civil Engineering",
    "Bachelor of Science in Business Administration",
    "Bachelor of Science in Computer Engineering",
    "Bachelor of Arts in Communication",
    "Bachelor of Science in Accountancy",
    "Bachelor of Science in Psychology",
    "Bachelor of Science in Tourism Management",
]
COURSES_SCHOLAR = [
    "DOST-SEI Scholarship – BS Physics",
    "DOST-SEI Scholarship – BS Mathematics",
    "CHED Scholarship – BS Education",
    "SM Foundation Scholarship – BS Business Administration",
    "SM Foundation Scholarship – BS Nursing",
    "Ayala Foundation Scholarship – BS Civil Engineering",
]
COURSES_PROFESSIONAL = [
    "Licensed Professional Teacher",
    "Registered Nurse (RN)",
    "Civil Engineer (CE)",
    "Information Technology Professional (ITP)",
    "Certified Public Accountant (CPA)",
    "Registered Electrical Engineer (REE)",
    "Registered Mechanical Engineer (RME)",
    "Doctor of Medicine (MD)",
    "Registered Nutritionist-Dietitian (RND)",
    "Licensed Social Worker (LSW)",
]
SCHOLARSHIP_TYPES = [
    "DOST-SEI Merit Scholarship",
    "SM Foundation Scholarship",
    "Ayala Foundation Scholarship",
    "DepEd Full Scholarship",
    "CHED Tertiary Education Subsidy",
    "Galing Pook Scholarship",
    "LGU Scholarship Grant",
    "PESFA Scholarship",
]
SECTIONS = ["Amethyst", "Diamond", "Emerald", "Garnet", "Jade",
            "Onyx", "Pearl", "Ruby", "Sapphire", "Topaz"]
YEAR_LEVELS = ["1st Year", "2nd Year", "3rd Year", "4th Year",
               "Grade 11", "Grade 12", "5th Year"]
BIOS = [
    "A dedicated learner committed to academic excellence and community service.",
    "Passionate about STEM and aspires to become a future innovator.",
    "Active in extracurricular activities and student government.",
    "A firm believer in the power of education to transform lives.",
    "Strives to make a positive impact in the community through leadership.",
    "A motivated scholar with a strong interest in science and technology.",
    "Values integrity, hard work, and continuous improvement.",
    "Actively participates in civic activities and school organizations.",
    "A creative thinker with a passion for arts and social entrepreneurship.",
    "Committed to becoming a catalyst for change in the region.",
]

ACTIVITIES_POOL = [
    ("Leadership Summit 2024",
     "A full-day leadership development summit featuring keynote speakers, workshops, and team-building activities designed to cultivate leadership skills among students and scholars."),
    ("Community Outreach Program",
     "Scholars and students visited partner communities to conduct literacy campaigns, health awareness sessions, and tree-planting activities."),
    ("Science and Technology Fair",
     "An exhibit showcasing innovative student research projects and inventions across various STEM disciplines."),
    ("Values Formation Seminar",
     "A values-oriented workshop focused on building character, ethics, and responsible citizenship among participants."),
    ("Career Orientation Forum",
     "Professionals from various industries shared career insights, trends, and scholarship opportunities with graduating students."),
    ("Environmental Awareness Camp",
     "A two-day eco-camp focused on environmental stewardship, waste segregation practices, and advocacy for sustainable development."),
    ("Financial Literacy Workshop",
     "A hands-on workshop teaching students the basics of budgeting, saving, and investing for their future."),
    ("Regional Youth Assembly",
     "A gathering of student leaders from across the region to discuss pressing issues affecting the youth and formulate policy recommendations."),
    ("Health and Wellness Seminar",
     "A health seminar covering topics such as mental health awareness, physical fitness, and proper nutrition for students."),
    ("Entrepreneurship Bootcamp",
     "A three-day intensive bootcamp on business planning, marketing, and social enterprise development for scholars and students."),
    ("Cultural Heritage Festival",
     "Celebrating the rich cultural heritage of the Philippines through traditional dances, folk music, and indigenous crafts exhibitions."),
    ("Anti-Drug Awareness Campaign",
     "An advocacy drive aimed at raising awareness among students about the dangers of illegal drugs and the importance of making healthy choices."),
    ("Disaster Risk Reduction Training",
     "A practical training on disaster preparedness, first aid, and emergency response procedures."),
    ("Technology Integration Symposium",
     "A symposium on leveraging technology in education, digital literacy, and responsible use of social media."),
    ("Reading Month Celebration",
     "A month-long program promoting a culture of reading through book fairs, storytelling contests, and library events."),
]

AWARD_TITLES = [
    "Outstanding Youth Leader Award",
    "Academic Excellence Award",
    "Most Outstanding Scholar",
    "Best in Leadership Development",
    "Community Service Award",
    "Excellence in Science and Technology",
    "Most Inspiring Student Leader",
    "Youth Achiever Award",
    "Best Campus Journalist",
    "Most Outstanding Researcher",
    "Social Entrepreneur of the Year",
    "Gawad Paglingkod Award",
    "Exemplary Service Award",
    "Leadership Excellence Award",
    "Pinnacle of Achievement Award",
]

AWARDING_BODIES = [
    "Department of Education (DepEd)",
    "Commission on Higher Education (CHED)",
    "National Youth Commission (NYC)",
    "Junior Chamber International Philippines",
    "Ten Outstanding Students of the Philippines Foundation",
    "SM Foundation Inc.",
    "Ayala Foundation Inc.",
    "Philippine Association of School Superintendents",
    "LGU Office of the Mayor",
    "Regional Development Council",
]

AWARD_DESCRIPTIONS = [
    "Awarded for demonstrating exceptional leadership qualities and inspiring peers through exemplary conduct and dedication to school and community.",
    "Recognized for maintaining the highest academic standing in the institution while actively participating in extracurricular and community activities.",
    "Honored for outstanding performance in leadership programs and significant contributions to the school's scholarship advocacy.",
    "Recipient of this award for spearheading community outreach initiatives and demonstrating remarkable volunteer spirit.",
    "Recognized for excellence in research and innovation, contributing valuable findings that benefit the local community.",
]

PHOTO_SEEDS_PEOPLE = list(range(10, 80))  # picsum.photos seeds for people
PHOTO_SEEDS_SCHOOLS = list(range(200, 220))
PHOTO_SEEDS_ACTIVITIES = list(range(300, 340))
PHOTO_SEEDS_CERTS = list(range(400, 450))

# ─────────────────────────────────────────────────────────────────────────────
# Schools master data
# ─────────────────────────────────────────────────────────────────────────────

SCHOOLS_DATA = [
    {
        "name": "Marikina National High School",
        "school_id": "NCR-300103",
        "school_type": "SECONDARY",
        "category": "Public / DepEd",
        "address": "Marikina Boulevard, Sto. Niño, Marikina City",
        "location": "Marikina City",
        "district": "District I",
        "division": "Marikina City Schools Division",
        "province": "Metro Manila",
        "region": "NCR – National Capital Region",
        "email": "marikina.nhs@deped.gov.ph",
        "phone": "(02) 8646-5432",
        "website": "https://marikina.deped.gov.ph",
        "founded_year": "1962",
        "img_seed": 201,
    },
    {
        "name": "Cebu City National Science High School",
        "school_id": "VII-700210",
        "school_type": "SECONDARY",
        "category": "Public / Science High School",
        "address": "Capitol Site, Escario Street, Cebu City",
        "location": "Cebu City",
        "district": "District V",
        "division": "Cebu City Schools Division",
        "province": "Cebu",
        "region": "Region VII – Central Visayas",
        "email": "ccnshs@deped.gov.ph",
        "phone": "(032) 253-7890",
        "website": "",
        "founded_year": "1975",
        "img_seed": 202,
    },
    {
        "name": "Davao City Integrated School",
        "school_id": "XI-110423",
        "school_type": "INTEGRATED",
        "category": "Public / DepEd / K–12 Integrated",
        "address": "C.M. Recto Avenue, Poblacion District, Davao City",
        "location": "Davao City",
        "district": "District III",
        "division": "Davao City Schools Division",
        "province": "Davao del Sur",
        "region": "Region XI – Davao Region",
        "email": "davao.integrated@deped.gov.ph",
        "phone": "(082) 221-5678",
        "website": "",
        "founded_year": "1948",
        "img_seed": 203,
    },
    {
        "name": "Iloilo City National High School",
        "school_id": "VI-600119",
        "school_type": "SECONDARY",
        "category": "Public / DepEd",
        "address": "Rizal Street, City Proper, Iloilo City",
        "location": "Iloilo City",
        "district": "District II",
        "division": "Iloilo City Schools Division",
        "province": "Iloilo",
        "region": "Region VI – Western Visayas",
        "email": "icnhs@deped.gov.ph",
        "phone": "(033) 335-1234",
        "website": "",
        "founded_year": "1955",
        "img_seed": 204,
    },
    {
        "name": "Batangas State University – Pablo Borbon Campus",
        "school_id": "IVA-400512",
        "school_type": "COLLEGE",
        "category": "State University / CHED",
        "address": "Rizal Avenue Extension, Batangas City",
        "location": "Batangas City",
        "district": "—",
        "division": "Batangas State University System",
        "province": "Batangas",
        "region": "Region IV-A – CALABARZON",
        "email": "info@batstate-u.edu.ph",
        "phone": "(043) 300-2201",
        "website": "https://www.batstate-u.edu.ph",
        "founded_year": "1903",
        "img_seed": 205,
    },
    {
        "name": "Polytechnic University of the Philippines – Manila",
        "school_id": "NCR-300887",
        "school_type": "COLLEGE",
        "category": "State University / CHED",
        "address": "Anonas Street, Sta. Mesa, Manila",
        "location": "Manila",
        "district": "—",
        "division": "PUP System",
        "province": "Metro Manila",
        "region": "NCR – National Capital Region",
        "email": "osas@pup.edu.ph",
        "phone": "(02) 8335-1787",
        "website": "https://www.pup.edu.ph",
        "founded_year": "1904",
        "img_seed": 206,
    },
    {
        "name": "Cagayan de Oro City National High School",
        "school_id": "X-1001234",
        "school_type": "SECONDARY",
        "category": "Public / DepEd",
        "address": "Don Apolinar Velez Street, Carmen, Cagayan de Oro City",
        "location": "Cagayan de Oro City",
        "district": "District I",
        "division": "Cagayan de Oro City Schools Division",
        "province": "Misamis Oriental",
        "region": "Region X – Northern Mindanao",
        "email": "cdocnhs@deped.gov.ph",
        "phone": "(088) 857-2345",
        "website": "",
        "founded_year": "1952",
        "img_seed": 207,
    },
    {
        "name": "Zamboanga National High School – Main",
        "school_id": "IX-900332",
        "school_type": "SECONDARY",
        "category": "Public / DepEd",
        "address": "Valderosa Street, Zone III, Zamboanga City",
        "location": "Zamboanga City",
        "district": "District II",
        "division": "Zamboanga City Schools Division",
        "province": "Zamboanga del Sur",
        "region": "Region IX – Zamboanga Peninsula",
        "email": "znhs.main@deped.gov.ph",
        "phone": "(062) 991-3456",
        "website": "",
        "founded_year": "1960",
        "img_seed": 208,
    },
    {
        "name": "Leyte National High School",
        "school_id": "VIII-800245",
        "school_type": "SECONDARY",
        "category": "Public / DepEd",
        "address": "P. Gomez Street, Downtown, Tacloban City",
        "location": "Tacloban City",
        "district": "District I",
        "division": "Leyte Schools Division",
        "province": "Leyte",
        "region": "Region VIII – Eastern Visayas",
        "email": "lnhs@deped.gov.ph",
        "phone": "(053) 321-4567",
        "website": "",
        "founded_year": "1945",
        "img_seed": 209,
    },
    {
        "name": "Baguio City National High School",
        "school_id": "CAR-140189",
        "school_type": "INTEGRATED",
        "category": "Public / DepEd / K–12 Integrated",
        "address": "Naguilian Road, Brgy. Quezon Hill, Baguio City",
        "location": "Baguio City",
        "district": "District I",
        "division": "Baguio City Schools Division",
        "province": "Benguet",
        "region": "CAR – Cordillera Administrative Region",
        "email": "bcnhs@deped.gov.ph",
        "phone": "(074) 442-5678",
        "website": "",
        "founded_year": "1909",
        "img_seed": 210,
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Principals master data (one per school, in same order as SCHOOLS_DATA)
# ─────────────────────────────────────────────────────────────────────────────

PRINCIPALS_DATA = [
    {
        "first_name": "Ricardo", "last_name": "Mendoza",
        "email": "ricardo.mendoza@marikina.deped.gov.ph",
        "contact_number": "09171234501",
        "address": "45 Sumulong Highway, Marikina City",
        "bio": "Dr. Ricardo Mendoza has served DepEd for 28 years, specializing in curriculum development and school administration. He led his school to three consecutive Brigada Eskwela national recognitions.",
        "student_id": "MNHS-P-2018",
        "year_level": "Principal III",
        "course_program": "Doctor of Education, Major in Educational Management – PLM",
        "year_started": "2018",
        "year_ended": "",
        "img_seed": 11,
        "gender": "M",
    },
    {
        "first_name": "Carmela", "last_name": "Santos",
        "email": "carmela.santos@cebudiv.deped.gov.ph",
        "contact_number": "09181234502",
        "address": "22 Leon Kilat Street, Cebu City",
        "bio": "Mrs. Carmela Santos is a seasoned educator and Science advocate with 23 years in DepEd. Under her leadership, CCNSHS produced multiple DOST-SEI scholars annually.",
        "student_id": "CCNSHS-P-2019",
        "year_level": "Principal II",
        "course_program": "Master of Arts in Science Education – USC",
        "year_started": "2019",
        "year_ended": "",
        "img_seed": 45,
        "gender": "F",
    },
    {
        "first_name": "Danilo", "last_name": "Reyes",
        "email": "danilo.reyes@davaocity.deped.gov.ph",
        "contact_number": "09191234503",
        "address": "88 Bonifacio Street, Davao City",
        "bio": "Mr. Danilo Reyes is a respected educator and community builder with 20 years of school leadership experience. He is a strong proponent of inclusive and values-based education.",
        "student_id": "DCIS-P-2020",
        "year_level": "Principal II",
        "course_program": "Master of Arts in Educational Management – ADDU",
        "year_started": "2020",
        "year_ended": "",
        "img_seed": 13,
        "gender": "M",
    },
    {
        "first_name": "Luzviminda", "last_name": "Garcia",
        "email": "luzviminda.garcia@iloilo.deped.gov.ph",
        "contact_number": "09201234504",
        "address": "9 Mabini Street, Iloilo City",
        "bio": "Dr. Luzviminda Garcia is a distinguished educator with 26 years in DepEd and a track record of raising school NAT scores. She champions Gender and Development programs school-wide.",
        "student_id": "ICNHS-P-2017",
        "year_level": "Principal III",
        "course_program": "Doctor of Philosophy in Education – CPU",
        "year_started": "2017",
        "year_ended": "",
        "img_seed": 46,
        "gender": "F",
    },
    {
        "first_name": "Eduardo", "last_name": "Villanueva",
        "email": "eduardo.villanueva@batstate-u.edu.ph",
        "contact_number": "09211234505",
        "address": "75 P. Burgos Street, Batangas City",
        "bio": "Engr. Eduardo Villanueva is a licensed Civil Engineer and academic administrator with 18 years in higher education. He is the driving force behind the university's research and development agenda.",
        "student_id": "BSU-P-2021",
        "year_level": "Campus Director II",
        "course_program": "Doctor of Engineering Management – DLSU",
        "year_started": "2021",
        "year_ended": "",
        "img_seed": 16,
        "gender": "M",
    },
    {
        "first_name": "Rosario", "last_name": "Tolentino",
        "email": "rosario.tolentino@pup.edu.ph",
        "contact_number": "09221234506",
        "address": "1 Doña Hemady Street, New Manila, Quezon City",
        "bio": "Prof. Rosario Tolentino is a veteran academic leader with 30 years of service in higher education and a prolific researcher in social sciences. She is known for her student-first administration style.",
        "student_id": "PUP-P-2016",
        "year_level": "Campus Director III",
        "course_program": "Doctor of Philosophy in Social Sciences – UP Diliman",
        "year_started": "2016",
        "year_ended": "",
        "img_seed": 47,
        "gender": "F",
    },
    {
        "first_name": "Virgilio", "last_name": "Castillo",
        "email": "virgilio.castillo@cdo.deped.gov.ph",
        "contact_number": "09231234507",
        "address": "34 Tiano Brothers Street, Cagayan de Oro City",
        "bio": "Mr. Virgilio Castillo is a respected school administrator and youth advocate with 22 years in DepEd Mindanao. He initiated the school's award-winning Leadership Development Program.",
        "student_id": "CDOCNHS-P-2018",
        "year_level": "Principal II",
        "course_program": "Master of Arts in Educational Management – XU",
        "year_started": "2018",
        "year_ended": "",
        "img_seed": 19,
        "gender": "M",
    },
    {
        "first_name": "Maricel", "last_name": "Aquino",
        "email": "maricel.aquino@zamboanga.deped.gov.ph",
        "contact_number": "09241234508",
        "address": "56 Mayor Jaldon Street, Zamboanga City",
        "bio": "Dr. Maricel Aquino has championed multilingual education and cultural inclusivity at ZNHS for 15 years. She holds a doctorate in Linguistics and has published research on mother tongue-based instruction.",
        "student_id": "ZNHS-P-2022",
        "year_level": "Principal I",
        "course_program": "Doctor of Philosophy in Linguistics – WMSU",
        "year_started": "2022",
        "year_ended": "",
        "img_seed": 48,
        "gender": "F",
    },
    {
        "first_name": "Ernesto", "last_name": "Flores",
        "email": "ernesto.flores@leyte.deped.gov.ph",
        "contact_number": "09251234509",
        "address": "12 Zamora Street, Tacloban City",
        "bio": "Mr. Ernesto Flores is a community-centered principal who rebuilt LNHS after Typhoon Yolanda. He has received the Outstanding Public School Principal award from DepEd Region VIII.",
        "student_id": "LNHS-P-2015",
        "year_level": "Principal III",
        "course_program": "Master of Science in Disaster Risk Management – VSU",
        "year_started": "2015",
        "year_ended": "",
        "img_seed": 22,
        "gender": "M",
    },
    {
        "first_name": "Gloria", "last_name": "Delos Santos",
        "email": "gloria.delossantos@baguio.deped.gov.ph",
        "contact_number": "09261234510",
        "address": "7 Abanao Street, Baguio City",
        "bio": "Dr. Gloria Delos Santos is an advocate for indigenous peoples' education and has integrated Ibaloi and Kankana-ey culture into the BCNHS curriculum. She earned recognition from NCIP for cultural integration efforts.",
        "student_id": "BCNHS-P-2020",
        "year_level": "Principal III",
        "course_program": "Doctor of Education in Indigenous Studies – UB",
        "year_started": "2020",
        "year_ended": "",
        "img_seed": 49,
        "gender": "F",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Helper: download image from picsum.photos
# ─────────────────────────────────────────────────────────────────────────────

def fetch_image(seed: int, width: int, height: int, filename: str):
    url = f"https://picsum.photos/seed/{seed}/{width}/{height}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        return ContentFile(data, name=filename)
    except Exception as exc:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Seed 10 Philippine schools with principals, students, activities, and leadership awards"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing seed data before inserting",
        )
        parser.add_argument(
            "--no-images",
            action="store_true",
            help="Skip downloading images (faster, no internet needed)",
        )

    def handle(self, *args, **options):
        rng = random.Random(42)  # deterministic

        if options["flush"]:
            self.stdout.write("  Flushing existing data...")
            LeadershipAward.objects.all().delete()
            Activity.objects.all().delete()
            # Delete all non-superuser, non-ADMIN persons/users (covers VIEWER/SCHOLAR/PROFESSIONAL/PRINCIPAL)
            Person.objects.exclude(user__is_superuser=True).exclude(user__role='ADMIN').delete()
            User.objects.filter(is_superuser=False).exclude(role='ADMIN').delete()
            School.objects.all().delete()
            self.stdout.write(self.style.WARNING("  Existing data cleared."))

        use_images = not options["no_images"]
        person_img_counter = [10]  # mutable counter for deterministic photo seeds

        def next_person_seed():
            s = person_img_counter[0]
            person_img_counter[0] += 1
            return s

        activity_img_counter = [300]

        def next_activity_seed():
            s = activity_img_counter[0]
            activity_img_counter[0] += 1
            return s

        cert_img_counter = [400]

        def next_cert_seed():
            s = cert_img_counter[0]
            cert_img_counter[0] += 1
            return s

        # ── helper: make a unique username ────────────────────────────────────
        def make_username(first, last, suffix=""):
            base = f"{first.lower().replace(' ', '')}.{last.lower().replace(' ', '')}"
            uname = f"{base}{suffix}"
            while User.objects.filter(username=uname).exists():
                uname = f"{base}{rng.randint(1, 999)}"
            return uname

        # ── helper: create a User + Person ────────────────────────────────────
        def create_person(
            first_name, last_name, email, role,
            person_type, school_obj, principal_user=None,
            extra_person=None, img_seed=None
        ):
            username = make_username(first_name, last_name)
            if User.objects.filter(email=email).exists():
                self.stdout.write(f"    [skip] {email} already exists")
                return None, None

            user = User.objects.create_user(
                username=username,
                email=email,
                password="@Password123",
                first_name=first_name,
                last_name=last_name,
                role=role,
                must_change_password=False,
            )
            person = Person(
                user=user,
                type=person_type,
                school=school_obj,
            )
            if extra_person:
                for k, v in extra_person.items():
                    setattr(person, k, v)

            if use_images and img_seed is not None:
                img_file = fetch_image(img_seed, 300, 300, f"profile_{username}.jpg")
                if img_file:
                    person.profile_photo.save(f"profile_{username}.jpg", img_file, save=False)

            person.save()
            return user, person

        # ═══════════════════════════════════════════════════════════════════════
        # 1. SCHOOLS
        # ═══════════════════════════════════════════════════════════════════════
        self.stdout.write(self.style.SUCCESS("\n[1/4] Creating schools..."))
        school_objects = []

        for i, sd in enumerate(SCHOOLS_DATA):
            if School.objects.filter(name=sd["name"]).exists():
                school_obj = School.objects.get(name=sd["name"])
                self.stdout.write(f"  [skip] {sd['name']} already exists")
            else:
                school_obj = School(
                    name=sd["name"],
                    school_id=sd["school_id"],
                    school_type=sd["school_type"],
                    category=sd["category"],
                    address=sd["address"],
                    location=sd["location"],
                    district=sd["district"],
                    division=sd["division"],
                    province=sd["province"],
                    region=sd["region"],
                    email=sd["email"],
                    phone=sd["phone"],
                    website=sd.get("website", ""),
                    founded_year=sd["founded_year"],
                    is_active=True,
                )
                seed = sd["img_seed"]
                if use_images:
                    logo_file = fetch_image(seed, 300, 300, f"logo_{i}.jpg")
                    banner_file = fetch_image(seed + 50, 1200, 400, f"banner_{i}.jpg")
                    if logo_file:
                        school_obj.logo.save(f"logo_{i}.jpg", logo_file, save=False)
                    if banner_file:
                        school_obj.banner.save(f"banner_{i}.jpg", banner_file, save=False)
                school_obj.save()
                self.stdout.write(f"  + {sd['name']}")
            school_objects.append(school_obj)

        # ═══════════════════════════════════════════════════════════════════════
        # 2. PRINCIPALS  (one per school)
        # ═══════════════════════════════════════════════════════════════════════
        self.stdout.write(self.style.SUCCESS("\n[2/4] Creating principals..."))
        principal_users = []

        for i, (pd, school_obj) in enumerate(zip(PRINCIPALS_DATA, school_objects)):
            email = pd["email"]
            if User.objects.filter(email=email).exists():
                user = User.objects.get(email=email)
                self.stdout.write(f"  [skip] {email}")
            else:
                user, person = create_person(
                    first_name=pd["first_name"],
                    last_name=pd["last_name"],
                    email=email,
                    role=User.Role.PRINCIPAL,
                    person_type=Person.Type.PRINCIPAL,
                    school_obj=school_obj,
                    extra_person={
                        "contact_number": pd["contact_number"],
                        "address": pd["address"],
                        "bio": pd["bio"],
                        "student_id": pd["student_id"],
                        "year_level": pd["year_level"],
                        "course_program": pd["course_program"],
                        "year_started": pd["year_started"],
                        "year_ended": pd.get("year_ended", ""),
                    },
                    img_seed=pd["img_seed"],
                )
                if user:
                    self.stdout.write(f"  + Principal {pd['first_name']} {pd['last_name']} → {school_obj.name}")

            # Assign principal to school (triggers SchoolPrincipalHistory)
            if user and school_obj.principal != user:
                school_obj.principal = user
                school_obj.save()

            principal_users.append(user)

        # ═══════════════════════════════════════════════════════════════════════
        # 3. STUDENTS / COLLEGE / SCHOLARS / PROFESSIONALS per school
        # ═══════════════════════════════════════════════════════════════════════
        self.stdout.write(self.style.SUCCESS("\n[3/4] Creating school members..."))

        # Pre-generate a big pool of unique name combinations
        name_pool = []
        for fn in MALE_FIRST + FEMALE_FIRST:
            for ln in LAST_NAMES:
                name_pool.append((fn, ln, "M" if fn in MALE_FIRST else "F"))
        rng.shuffle(name_pool)
        name_idx = [0]

        def next_name():
            n = name_pool[name_idx[0] % len(name_pool)]
            name_idx[0] += 1
            return n

        school_person_map = {}  # school_id → list of non-principal Person objects

        COMPOSITION = [
            # (count, role, type, course_list, extra_builder)
            (5, User.Role.VIEWER, Person.Type.STUDENT, COURSES_STUDENT),
            (5, User.Role.VIEWER, Person.Type.COLLEGE, COURSES_COLLEGE),
            (2, User.Role.SCHOLAR, Person.Type.SCHOLAR, COURSES_SCHOLAR),
            (1, User.Role.PROFESSIONAL, Person.Type.PROFESSIONAL, COURSES_PROFESSIONAL),
        ]

        for school_obj in school_objects:
            school_person_map[school_obj.pk] = []
            school_slug = school_obj.name[:10].replace(" ", "").lower()

            for count, role, ptype, courses in COMPOSITION:
                for _ in range(count):
                    fn, ln, gender = next_name()
                    email_domain = school_obj.email.split("@")[-1] if school_obj.email else "school.edu.ph"
                    uname_base = make_username(fn, ln)
                    email = f"{uname_base}@{email_domain}"
                    # Ensure email uniqueness
                    suffix_n = 1
                    while User.objects.filter(email=email).exists():
                        email = f"{uname_base}{suffix_n}@{email_domain}"
                        suffix_n += 1

                    course = rng.choice(courses)
                    section = rng.choice(SECTIONS)
                    yr_level = rng.choice(YEAR_LEVELS)
                    yr_start = str(rng.randint(2018, 2023))
                    yr_end = str(int(yr_start) + rng.randint(1, 4)) if ptype != Person.Type.PROFESSIONAL else ""
                    bio = rng.choice(BIOS)
                    s_id = f"{school_obj.school_id[:6].replace('-', '')}-{ptype[:3]}-{rng.randint(1000, 9999)}"

                    extra = {
                        "contact_number": f"09{rng.randint(100000000, 999999999)}",
                        "address": f"Brgy. {rng.choice(['San Jose', 'Sta. Cruz', 'Poblacion', 'San Pedro', 'Magsaysay'])}, {school_obj.location}",
                        "bio": bio,
                        "student_id": s_id,
                        "year_level": yr_level,
                        "course_program": course,
                        "section": section,
                        "year_started": yr_start,
                        "year_ended": yr_end,
                    }
                    if ptype == Person.Type.SCHOLAR:
                        extra["scholarship_type"] = rng.choice(SCHOLARSHIP_TYPES)

                    img_seed = next_person_seed()
                    user, person = create_person(
                        first_name=fn,
                        last_name=ln,
                        email=email,
                        role=role,
                        person_type=ptype,
                        school_obj=school_obj,
                        extra_person=extra,
                        img_seed=img_seed,
                    )
                    if person:
                        school_person_map[school_obj.pk].append(person)

            self.stdout.write(
                f"  + {school_obj.name}: {len(school_person_map[school_obj.pk])} members"
            )

        # ═══════════════════════════════════════════════════════════════════════
        # 4. ACTIVITIES per school (1–5 each)
        # ═══════════════════════════════════════════════════════════════════════
        self.stdout.write(self.style.SUCCESS("\n[4a/4] Creating activities..."))

        act_pool = ACTIVITIES_POOL.copy()
        rng.shuffle(act_pool)
        act_idx = [0]

        def next_activity():
            a = act_pool[act_idx[0] % len(act_pool)]
            act_idx[0] += 1
            return a

        today = date.today()
        school_activity_map = {}

        for school_obj, principal_user in zip(school_objects, principal_users):
            count = rng.randint(2, 5)
            school_activity_map[school_obj.pk] = []
            members = school_person_map.get(school_obj.pk, [])

            for _ in range(count):
                a_name, a_desc = next_activity()
                # Mix past and upcoming dates
                offset = rng.randint(-300, 120)
                a_date = today + timedelta(days=offset)
                is_approved = rng.random() > 0.2
                img_seed = next_activity_seed()

                activity = Activity(
                    name=a_name,
                    date=a_date,
                    description=a_desc,
                    school=school_obj,
                    is_approved=is_approved,
                    approved_by=principal_user if is_approved else None,
                )
                if use_images:
                    img_file = fetch_image(img_seed, 1200, 400, f"activity_{img_seed}.jpg")
                    if img_file:
                        activity.banner.save(f"activity_{img_seed}.jpg", img_file, save=False)
                activity.save()

                # Add random school members as participants
                if members:
                    k = min(len(members), rng.randint(3, len(members)))
                    for p in rng.sample(members, k):
                        p.activities.add(activity)

                school_activity_map[school_obj.pk].append(activity)
                self.stdout.write(f"  + {a_name[:40]} → {school_obj.name[:25]}")

        # ═══════════════════════════════════════════════════════════════════════
        # 5. LEADERSHIP AWARDS  (randomly assigned, non-principal)
        # ═══════════════════════════════════════════════════════════════════════
        self.stdout.write(self.style.SUCCESS("\n[4b/4] Creating leadership awards..."))

        LEVELS = list(LeadershipAward.AwardLevel.values)

        for school_obj in school_objects:
            members = school_person_map.get(school_obj.pk, [])
            if not members:
                continue

            # Give 2–5 awards per school
            num_awards = rng.randint(2, 5)
            # Allow multiple awards to the same person (they may excel in different areas)
            awardees = rng.choices(members, k=num_awards)

            for person in awardees:
                title = rng.choice(AWARD_TITLES)
                year = str(rng.randint(2019, 2024))
                level = rng.choice(LEVELS)
                body = rng.choice(AWARDING_BODIES)
                desc = rng.choice(AWARD_DESCRIPTIONS)
                img_seed = next_cert_seed()

                award = LeadershipAward(
                    recipient=person,
                    award_title=title,
                    award_level=level,
                    year_awarded=year,
                    awarding_body=body,
                    description=desc,
                    school=school_obj,
                )
                if use_images:
                    cert_file = fetch_image(img_seed, 800, 600, f"cert_{img_seed}.jpg")
                    if cert_file:
                        award.certificate.save(f"cert_{img_seed}.jpg", cert_file, save=False)
                award.save()
                self.stdout.write(
                    f"  + {title[:35]} → {person.user.get_full_name()} ({school_obj.name[:20]})"
                )

        # ─────────────────────────────────────────────────────────────────────
        # Summary
        # ─────────────────────────────────────────────────────────────────────
        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(self.style.SUCCESS("Seed complete!"))
        self.stdout.write(f"  Schools:          {School.objects.count()}")
        self.stdout.write(f"  Users:            {User.objects.count()}")
        self.stdout.write(f"  Persons:          {Person.objects.count()}")
        self.stdout.write(f"  Activities:       {Activity.objects.count()}")
        self.stdout.write(f"  Leadership Awards:{LeadershipAward.objects.count()}")
        self.stdout.write("═" * 60)
