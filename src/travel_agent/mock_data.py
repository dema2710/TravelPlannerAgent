"""Deterministic mock catalogue for seven European destinations.

Everything in this module is simulated sample data. It exists to make the
assignment reproducible and testable without external APIs. It is not live
weather, availability, or pricing information.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ClimateMonth:
    """Typical simulated high/low temperatures and rain probability."""

    high_c: int
    low_c: int
    rain_probability: int


@dataclass(frozen=True)
class HotelSeed:
    name: str
    category: str
    base_price_per_night_eur: float
    rating: float
    location: str


@dataclass(frozen=True)
class AttractionSeed:
    name: str
    category: str
    description: str
    duration_hours: float
    price_eur: float
    opening_hours: tuple[str, str] | None
    closed_weekdays: tuple[int, ...]
    interests: tuple[str, ...]
    dietary_tags: tuple[str, ...] = ()
    meal_type: str | None = None
    location: str | None = None


@dataclass(frozen=True)
class DepartureCity:
    """A simulated departure airport profile."""

    key: str
    name: str
    country: str
    airport_code: str
    aliases: tuple[str, ...]
    price_factor: float
    timezone_offset_minutes: int


@dataclass(frozen=True)
class CityProfile:
    key: str
    name: str
    country: str
    airport_code: str
    aliases: tuple[str, ...]
    flight_base_eur: float
    food_per_day_eur: float
    local_transport_per_day_eur: float
    climate: tuple[ClimateMonth, ...]
    hotels: tuple[HotelSeed, ...]
    attractions: tuple[AttractionSeed, ...]


# Simulated seasonal multipliers applied to flights and hotels.
SEASON_FACTORS: dict[int, float] = {
    1: 0.82,
    2: 0.85,
    3: 0.90,
    4: 1.00,
    5: 1.08,
    6: 1.15,
    7: 1.20,
    8: 1.20,
    9: 1.10,
    10: 1.00,
    11: 0.88,
    12: 0.98,
}

DEFAULT_DEPARTURE_CITY = "Prague"
DESTINATION_TIMEZONE_OFFSET_MINUTES = 60

# Simulated departure airports. Price factors scale the destination base fares
# deterministically for every supported origin.
DEPARTURE_CITIES: dict[str, DepartureCity] = {
    "PRAGUE": DepartureCity(
        key="prague",
        name="Prague",
        country="Czech Republic",
        airport_code="PRG",
        aliases=("prague", "praha"),
        price_factor=0.72,
        timezone_offset_minutes=60,
    ),
    "BERLIN": DepartureCity(
        key="berlin",
        name="Berlin",
        country="Germany",
        airport_code="BER",
        aliases=("berlin",),
        price_factor=0.78,
        timezone_offset_minutes=60,
    ),
    "VIENNA": DepartureCity(
        key="vienna",
        name="Vienna",
        country="Austria",
        airport_code="VIE",
        aliases=("vienna", "wien"),
        price_factor=0.75,
        timezone_offset_minutes=60,
    ),
    "LONDON": DepartureCity(
        key="london",
        name="London",
        country="United Kingdom",
        airport_code="LGW",
        aliases=("london",),
        price_factor=1.00,
        timezone_offset_minutes=0,
    ),
}

# Route-specific simulated flight durations in minutes. Unlisted pairs (such as
# a same-city trip) are rejected by the flight tool.
ROUTE_FLIGHT_MINUTES: dict[tuple[str, str], int] = {
    ("prague", "paris"): 115,
    ("prague", "rome"): 135,
    ("prague", "berlin"): 60,
    ("prague", "amsterdam"): 125,
    ("prague", "vienna"): 60,
    ("prague", "barcelona"): 165,
    ("berlin", "paris"): 105,
    ("berlin", "rome"): 140,
    ("berlin", "prague"): 60,
    ("berlin", "amsterdam"): 90,
    ("berlin", "vienna"): 85,
    ("berlin", "barcelona"): 165,
    ("vienna", "paris"): 135,
    ("vienna", "rome"): 120,
    ("vienna", "prague"): 60,
    ("vienna", "berlin"): 85,
    ("vienna", "amsterdam"): 130,
    ("vienna", "barcelona"): 155,
    ("london", "paris"): 75,
    ("london", "prague"): 130,
    ("london", "rome"): 165,
    ("london", "berlin"): 110,
    ("london", "amsterdam"): 80,
    ("london", "vienna"): 145,
    ("london", "barcelona"): 140,
}

AIRLINES: tuple[dict[str, object], ...] = (
    {
        "name": "Aurora Air",
        "price_factor": 0.80,
        "outbound_departure": "06:35",
        "return_departure": "21:10",
        "stops": 0,
    },
    {
        "name": "EuroWings Connect",
        "price_factor": 1.00,
        "outbound_departure": "10:20",
        "return_departure": "18:15",
        "stops": 0,
    },
    {
        "name": "Blue Horizon",
        "price_factor": 1.22,
        "outbound_departure": "14:10",
        "return_departure": "11:40",
        "stops": 0,
    },
    {
        "name": "Continental Express",
        "price_factor": 0.92,
        "outbound_departure": "18:45",
        "return_departure": "07:25",
        "stops": 1,
    },
)


CITIES: dict[str, CityProfile] = {
    "PARIS": CityProfile(
        key="paris",
        name="Paris",
        country="France",
        airport_code="CDG",
        aliases=("paris", "ville lumière"),
        flight_base_eur=185.0,
        food_per_day_eur=58.0,
        local_transport_per_day_eur=8.0,
        climate=(
            ClimateMonth(8, 3, 55), ClimateMonth(9, 3, 48),
            ClimateMonth(13, 6, 50), ClimateMonth(16, 8, 48),
            ClimateMonth(20, 12, 55), ClimateMonth(23, 15, 52),
            ClimateMonth(26, 17, 45), ClimateMonth(26, 17, 46),
            ClimateMonth(22, 14, 50), ClimateMonth(16, 10, 58),
            ClimateMonth(11, 6, 60), ClimateMonth(8, 4, 60),
        ),
        hotels=(
            HotelSeed("Hôtel du Canal Saint-Martin", "budget", 72, 3.6, "10th arrondissement"),
            HotelSeed("Maison Montparnasse", "midscale", 106, 4.2, "Montparnasse"),
            HotelSeed("Hôtel des Arts Rive Gauche", "boutique", 158, 4.6, "Saint-Germain-des-Prés"),
            HotelSeed("Grand Hôtel Lumière", "upscale", 245, 4.8, "Opéra"),
        ),
        attractions=(
            AttractionSeed(
                "Louvre Museum", "museums",
                "World-famous museum with classical and modern collections.",
                3.0, 22.0, ("09:00", "18:00"), (1,), ("museums", "art", "history"),
                location="1st arrondissement",
            ),
            AttractionSeed(
                "Musée d'Orsay", "museums",
                "Impressionist masterpieces in a converted railway station.",
                2.5, 16.0, ("09:30", "18:00"), (0,), ("museums", "art"),
                location="7th arrondissement",
            ),
            AttractionSeed(
                "Notre-Dame Cathedral", "architecture",
                "Gothic cathedral on the Île de la Cité (exterior visit).",
                1.0, 0.0, ("08:00", "18:45"), (), ("architecture", "history"),
                location="Île de la Cité",
            ),
            AttractionSeed(
                "Eiffel Tower", "architecture",
                "Iconic iron tower with city views from the second floor.",
                2.0, 29.50, ("09:30", "23:00"), (), ("architecture", "history"),
                location="7th arrondissement",
            ),
            AttractionSeed(
                "Sainte-Chapelle", "architecture",
                "Gothic chapel renowned for its stained-glass windows.",
                1.0, 13.0, ("09:00", "19:00"), (), ("architecture", "history"),
                location="Île de la Cité",
            ),
            AttractionSeed(
                "Montmartre & Sacré-Cœur Walk", "architecture",
                "Self-guided walk through Montmartre's streets and viewpoints.",
                2.0, 0.0, ("08:00", "20:00"), (), ("architecture", "history"),
                location="Montmartre",
            ),
            AttractionSeed(
                "Luxembourg Gardens", "nature",
                "Formal gardens, tree-lined paths, and quiet corners.",
                1.5, 0.0, ("07:30", "21:00"), (), ("nature",),
                location="6th arrondissement",
            ),
            AttractionSeed(
                "Seine River Evening Cruise", "entertainment",
                "One-hour simulated sightseeing cruise along the Seine.",
                1.0, 17.0, ("10:00", "22:00"), (), ("entertainment", "architecture"),
                location="Port de la Bourdonnais",
            ),
            AttractionSeed(
                "Le Marais Food Walk", "food",
                "Sample market bites and pastries while exploring Le Marais.",
                3.0, 45.0, ("11:00", "18:00"), (0,), ("food", "history"),
                dietary_tags=("omnivore",), meal_type="lunch", location="Le Marais",
            ),
            AttractionSeed(
                "Végétale Marais", "food",
                "Vegetarian bistro with seasonal French dishes.",
                1.5, 24.0, ("12:00", "22:00"), (), ("food",),
                dietary_tags=("vegetarian", "vegan", "gluten_free"),
                meal_type="dinner", location="Le Marais",
            ),
            AttractionSeed(
                "Bistro du Canal", "food",
                "Neighbourhood bistro with vegetarian and halal options.",
                1.5, 31.0, ("12:00", "23:00"), (), ("food",),
                dietary_tags=("vegetarian", "halal"), meal_type="dinner",
                location="Canal Saint-Martin",
            ),
            AttractionSeed(
                "Vintage Shops of Le Marais", "shopping",
                "Independent vintage and design shops around the Marais.",
                2.0, 0.0, ("10:00", "19:00"), (6,), ("shopping",),
                location="Le Marais",
            ),
        ),
    ),
    "PRAGUE": CityProfile(
        key="prague",
        name="Prague",
        country="Czech Republic",
        airport_code="PRG",
        aliases=("prague", "praha"),
        flight_base_eur=145.0,
        food_per_day_eur=32.0,
        local_transport_per_day_eur=5.0,
        climate=(
            ClimateMonth(3, -2, 45), ClimateMonth(5, -1, 40),
            ClimateMonth(9, 2, 42), ClimateMonth(15, 5, 40),
            ClimateMonth(20, 10, 50), ClimateMonth(23, 13, 55),
            ClimateMonth(25, 15, 52), ClimateMonth(25, 15, 50),
            ClimateMonth(20, 11, 45), ClimateMonth(14, 7, 42),
            ClimateMonth(7, 2, 50), ClimateMonth(4, -1, 48),
        ),
        hotels=(
            HotelSeed("Vltava Budget Rooms", "budget", 42, 3.5, "Holešovice"),
            HotelSeed("Old Town Court Hotel", "midscale", 68, 4.2, "Old Town"),
            HotelSeed("Design Hotel Karlín", "boutique", 108, 4.6, "Karlín"),
            HotelSeed("Grand Bohemia Palace", "upscale", 175, 4.8, "New Town"),
        ),
        attractions=(
            AttractionSeed(
                "Prague Castle", "history",
                "Hilltop castle complex with courtyards, churches, and views.",
                3.0, 15.0, ("09:00", "17:00"), (), ("history", "architecture"),
                location="Hradčany",
            ),
            AttractionSeed(
                "Charles Bridge", "architecture",
                "Historic stone bridge lined with statues over the Vltava.",
                1.0, 0.0, ("00:00", "23:59"), (), ("architecture", "history"),
                location="Old Town",
            ),
            AttractionSeed(
                "Old Town Hall & Astronomical Clock", "history",
                "Medieval town hall and the famous astronomical clock.",
                1.5, 13.0, ("09:00", "19:00"), (0,), ("history", "architecture"),
                location="Old Town Square",
            ),
            AttractionSeed(
                "St. Vitus Cathedral", "architecture",
                "Gothic cathedral inside Prague Castle with stained glass.",
                1.5, 8.0, ("09:00", "17:00"), (), ("architecture", "history"),
                location="Prague Castle",
            ),
            AttractionSeed(
                "Museum of Communism", "museums",
                "Exhibits on everyday life and politics under communism.",
                1.5, 10.0, ("09:00", "20:00"), (), ("museums", "history"),
                location="Václavské náměstí",
            ),
            AttractionSeed(
                "Petřín Hill & Lookout", "nature",
                "Wooded hill with walking paths and a small lookout tower.",
                2.0, 6.0, ("09:00", "20:00"), (), ("nature",),
                location="Malá Strana",
            ),
            AttractionSeed(
                "Vltava River Cruise", "entertainment",
                "Short sightseeing cruise beneath Prague's bridges.",
                1.0, 14.0, ("10:00", "20:00"), (), ("entertainment", "architecture"),
                location="Náplavka",
            ),
            AttractionSeed(
                "Josefov Jewish Quarter Walk", "history",
                "Self-guided walk through the historic Jewish quarter.",
                2.0, 12.0, ("09:00", "17:00"), (5,), ("history",),
                location="Josefov",
            ),
            AttractionSeed(
                "Vegan Bistro Máj", "food",
                "Plant-based bistro serving Czech-inspired lunches.",
                1.5, 14.0, ("11:00", "21:00"), (), ("food",),
                dietary_tags=("vegan", "vegetarian", "gluten_free"), meal_type="lunch",
                location="Nové Město",
            ),
            AttractionSeed(
                "Czech Vegetarian Kitchen", "food",
                "Traditional dishes adapted for vegetarian diets.",
                1.5, 18.0, ("11:30", "22:00"), (), ("food",),
                dietary_tags=("vegetarian", "gluten_free"), meal_type="dinner",
                location="Vinohrady",
            ),
            AttractionSeed(
                "Beer Garden Letná", "food",
                "Relaxed garden with simple vegetarian plates and local drinks.",
                1.5, 12.0, ("11:00", "22:00"), (), ("food", "entertainment"),
                dietary_tags=("vegetarian",), meal_type="dinner", location="Letná",
            ),
            AttractionSeed(
                "Kafka Museum", "museums",
                "Small museum exploring Franz Kafka's life and Prague.",
                2.0, 12.0, ("10:00", "18:00"), (), ("museums", "history"),
                location="Malá Strana",
            ),
        ),
    ),
    "ROME": CityProfile(
        key="rome",
        name="Rome",
        country="Italy",
        airport_code="FCO",
        aliases=("rome", "roma"),
        flight_base_eur=210.0,
        food_per_day_eur=48.0,
        local_transport_per_day_eur=7.0,
        climate=(
            ClimateMonth(13, 4, 50), ClimateMonth(14, 4, 45),
            ClimateMonth(17, 6, 42), ClimateMonth(20, 9, 45),
            ClimateMonth(25, 13, 35), ClimateMonth(29, 17, 25),
            ClimateMonth(32, 20, 15), ClimateMonth(32, 20, 20),
            ClimateMonth(28, 17, 35), ClimateMonth(23, 13, 50),
            ClimateMonth(17, 9, 58), ClimateMonth(14, 5, 55),
        ),
        hotels=(
            HotelSeed("Trastevere Simple Stay", "budget", 68, 3.7, "Trastevere"),
            HotelSeed("Domus Monti", "midscale", 112, 4.3, "Monti"),
            HotelSeed("Palazzo Navona Boutique", "boutique", 175, 4.6, "Piazza Navona"),
            HotelSeed("Grand Roma Imperiale", "upscale", 260, 4.8, "Via Veneto"),
        ),
        attractions=(
            AttractionSeed(
                "Colosseum", "history",
                "Ancient amphitheatre and symbol of imperial Rome.",
                2.5, 18.0, ("08:30", "19:00"), (), ("history", "architecture"),
                location="Celio",
            ),
            AttractionSeed(
                "Roman Forum & Palatine Hill", "history",
                "Ruins of the ancient civic centre and imperial palaces.",
                3.0, 18.0, ("09:00", "18:00"), (), ("history", "architecture"),
                location="Parco archeologico del Colosseo",
            ),
            AttractionSeed(
                "Vatican Museums & Sistine Chapel", "museums",
                "Extensive art collections and the Sistine Chapel.",
                4.0, 20.0, ("08:00", "19:00"), (6,), ("museums", "art", "history"),
                location="Vatican City",
            ),
            AttractionSeed(
                "St. Peter's Basilica", "architecture",
                "Renaissance basilica with a monumental interior.",
                2.0, 0.0, ("07:00", "19:00"), (), ("architecture", "history"),
                location="Vatican City",
            ),
            AttractionSeed(
                "Pantheon", "architecture",
                "Well-preserved Roman temple with a spectacular dome.",
                1.0, 5.0, ("09:00", "19:00"), (), ("architecture", "history"),
                location="Centro Storico",
            ),
            AttractionSeed(
                "Trevi Fountain & Spanish Steps Walk", "architecture",
                "Classic walking route through central Rome's squares.",
                1.5, 0.0, ("00:00", "23:59"), (), ("architecture", "history"),
                location="Centro Storico",
            ),
            AttractionSeed(
                "Borghese Gardens", "nature",
                "Landscaped park with paths, viewpoints, and galleries nearby.",
                2.0, 0.0, ("07:00", "21:00"), (), ("nature",),
                location="Pinciano",
            ),
            AttractionSeed(
                "Trastevere Food Walk", "food",
                "Evening walk with samples from local bakeries and trattorias.",
                3.0, 40.0, ("17:00", "22:00"), (), ("food", "history"),
                dietary_tags=("vegetarian",), meal_type="dinner", location="Trastevere",
            ),
            AttractionSeed(
                "Vegetarian Roman Cooking Class", "food",
                "Hands-on class preparing vegetarian versions of Roman dishes.",
                2.5, 55.0, ("18:00", "21:00"), (), ("food", "entertainment"),
                dietary_tags=("vegetarian", "vegan"), meal_type="dinner",
                location="Testaccio",
            ),
            AttractionSeed(
                "Tonnarello Vegano", "food",
                "Plant-based pasta and small plates near the river.",
                1.5, 22.0, ("12:00", "23:00"), (), ("food",),
                dietary_tags=("vegan", "vegetarian"), meal_type="dinner",
                location="Trastevere",
            ),
            AttractionSeed(
                "Pasta Fresca Monti", "food",
                "Casual pasta kitchen with vegetarian choices.",
                1.5, 19.0, ("12:00", "22:30"), (), ("food",),
                dietary_tags=("vegetarian",), meal_type="lunch", location="Monti",
            ),
        ),
    ),
    "BERLIN": CityProfile(
        key="berlin",
        name="Berlin",
        country="Germany",
        airport_code="BER",
        aliases=("berlin",),
        flight_base_eur=160.0,
        food_per_day_eur=42.0,
        local_transport_per_day_eur=6.0,
        climate=(
            ClimateMonth(3, -1, 50), ClimateMonth(5, -1, 45),
            ClimateMonth(9, 2, 42), ClimateMonth(15, 5, 38),
            ClimateMonth(20, 10, 45), ClimateMonth(23, 13, 48),
            ClimateMonth(25, 15, 45), ClimateMonth(25, 15, 45),
            ClimateMonth(20, 11, 42), ClimateMonth(14, 7, 48),
            ClimateMonth(7, 3, 52), ClimateMonth(4, 0, 52),
        ),
        hotels=(
            HotelSeed("Spree Side Budget Rooms", "budget", 55, 3.6, "Friedrichshain"),
            HotelSeed("Mitte Comfort Hotel", "midscale", 88, 4.1, "Mitte"),
            HotelSeed("Kreuzberg Design Loft", "boutique", 135, 4.5, "Kreuzberg"),
            HotelSeed("Grand Berlin Residenz", "upscale", 215, 4.7, "Charlottenburg"),
        ),
        attractions=(
            AttractionSeed(
                "Museum Island", "museums",
                "UNESCO-listed island with several major museums.",
                4.0, 24.0, ("10:00", "18:00"), (0,), ("museums", "art", "history"),
                location="Mitte",
            ),
            AttractionSeed(
                "Brandenburg Gate & Reichstag", "history",
                "Historic gate and the glass dome of the Reichstag building.",
                2.0, 0.0, ("08:00", "22:00"), (), ("history", "architecture"),
                location="Mitte",
            ),
            AttractionSeed(
                "East Side Gallery", "art",
                "Open-air gallery on a preserved section of the Berlin Wall.",
                1.5, 0.0, ("00:00", "23:59"), (), ("art", "history"),
                location="Friedrichshain",
            ),
            AttractionSeed(
                "Berlin Wall Memorial", "history",
                "Documentation centre and preserved border strip.",
                2.0, 0.0, ("08:00", "20:00"), (), ("history",),
                location="Bernauer Straße",
            ),
            AttractionSeed(
                "TV Tower", "entertainment",
                "Observation deck with panoramic city views.",
                1.5, 25.0, ("09:00", "23:00"), (), ("entertainment", "architecture"),
                location="Alexanderplatz",
            ),
            AttractionSeed(
                "Tempelhofer Feld", "nature",
                "Former airfield turned public park and cycling space.",
                2.0, 0.0, ("06:00", "22:00"), (), ("nature", "entertainment"),
                location="Tempelhof",
            ),
            AttractionSeed(
                "Charlottenburg Palace", "architecture",
                "Baroque palace with formal gardens and state rooms.",
                2.5, 12.0, ("10:00", "17:30"), (0,), ("architecture", "history"),
                location="Charlottenburg",
            ),
            AttractionSeed(
                "Spree River Cruise", "entertainment",
                "Short boat tour past central Berlin landmarks.",
                1.0, 18.0, ("10:00", "20:00"), (), ("entertainment",),
                location="Mitte",
            ),
            AttractionSeed(
                "Veggie Berlin Mitte", "food",
                "Vegetarian café with bowls, soups, and cakes.",
                1.5, 18.0, ("09:00", "21:00"), (), ("food",),
                dietary_tags=("vegetarian", "vegan", "gluten_free"), meal_type="lunch",
                location="Mitte",
            ),
            AttractionSeed(
                "Markthalle Neun Street Food", "food",
                "Indoor market with many vegetarian street-food stalls.",
                2.0, 15.0, ("12:00", "21:00"), (0,), ("food", "shopping"),
                dietary_tags=("vegetarian",), meal_type="lunch", location="Kreuzberg",
            ),
            AttractionSeed(
                "Berliner Kaffeehaus", "food",
                "Traditional-style café for coffee and a light vegetarian meal.",
                1.0, 10.0, ("08:00", "18:00"), (), ("food",),
                dietary_tags=("vegetarian",), meal_type="breakfast", location="Prenzlauer Berg",
            ),
        ),
    ),
    "AMSTERDAM": CityProfile(
        key="amsterdam",
        name="Amsterdam",
        country="Netherlands",
        airport_code="AMS",
        aliases=("amsterdam",),
        flight_base_eur=150.0,
        food_per_day_eur=50.0,
        local_transport_per_day_eur=8.0,
        climate=(
            ClimateMonth(6, 2, 60), ClimateMonth(7, 2, 55),
            ClimateMonth(10, 4, 52), ClimateMonth(14, 6, 45),
            ClimateMonth(18, 10, 48), ClimateMonth(21, 13, 50),
            ClimateMonth(23, 15, 52), ClimateMonth(23, 15, 55),
            ClimateMonth(20, 12, 58), ClimateMonth(15, 9, 60),
            ClimateMonth(10, 5, 62), ClimateMonth(7, 3, 65),
        ),
        hotels=(
            HotelSeed("Canal Ring Budget Rooms", "budget", 82, 3.5, "Jordaan"),
            HotelSeed("Museum Quarter Hotel", "midscale", 128, 4.2, "Museumplein"),
            HotelSeed("De Pijp Boutique House", "boutique", 185, 4.6, "De Pijp"),
            HotelSeed("Grand Amstel Residence", "upscale", 290, 4.8, "Amstel"),
        ),
        attractions=(
            AttractionSeed(
                "Rijksmuseum", "museums",
                "Dutch Golden Age art and history in a grand museum.",
                3.0, 25.0, ("09:00", "17:00"), (), ("museums", "art", "history"),
                location="Museumplein",
            ),
            AttractionSeed(
                "Van Gogh Museum", "museums",
                "Large collection of Van Gogh paintings and letters.",
                2.5, 24.0, ("09:00", "18:00"), (), ("museums", "art"),
                location="Museumplein",
            ),
            AttractionSeed(
                "Anne Frank House", "history",
                "Museum in the former hiding place of Anne Frank.",
                1.5, 16.0, ("09:00", "22:00"), (), ("history",),
                location="Centrum",
            ),
            AttractionSeed(
                "Canal Cruise", "entertainment",
                "Sightseeing cruise through Amsterdam's canal ring.",
                1.0, 20.0, ("09:00", "22:00"), (), ("entertainment", "architecture"),
                location="Centraal Station",
            ),
            AttractionSeed(
                "Jordaan Walking Tour", "architecture",
                "Guided walk through narrow streets and canal-side courtyards.",
                2.0, 15.0, ("10:00", "18:00"), (), ("architecture", "history"),
                location="Jordaan",
            ),
            AttractionSeed(
                "Vondelpark", "nature",
                "Large urban park with ponds, cafés, and cycling paths.",
                1.5, 0.0, ("06:00", "22:00"), (), ("nature",),
                location="Oud-West",
            ),
            AttractionSeed(
                "Zaanse Schans Day Trip", "architecture",
                "Simulated half-day trip to windmills and traditional houses.",
                4.0, 35.0, ("09:00", "17:00"), (), ("architecture", "nature"),
                location="Zaanse Schans",
            ),
            AttractionSeed(
                "NEMO Science Museum", "museums",
                "Interactive science museum with a rooftop viewpoint.",
                2.5, 19.50, ("10:00", "17:30"), (), ("museums", "entertainment"),
                location="Oosterdok",
            ),
            AttractionSeed(
                "Vegan Junk Food Bar", "food",
                "Plant-based burgers and snacks in a casual setting.",
                1.0, 16.0, ("12:00", "22:00"), (), ("food",),
                dietary_tags=("vegan", "vegetarian"), meal_type="lunch",
                location="De Pijp",
            ),
            AttractionSeed(
                "De Waaghals", "food",
                "Vegetarian restaurant with seasonal international dishes.",
                1.5, 27.0, ("17:30", "22:00"), (), ("food",),
                dietary_tags=("vegetarian", "vegan"), meal_type="dinner",
                location="De Pijp",
            ),
            AttractionSeed(
                "Albert Cuyp Market", "food",
                "Busy street market with vegetarian snack options.",
                1.5, 12.0, ("09:00", "17:00"), (6,), ("food", "shopping"),
                dietary_tags=("vegetarian",), meal_type="lunch", location="De Pijp",
            ),
        ),
    ),
    "VIENNA": CityProfile(
        key="vienna",
        name="Vienna",
        country="Austria",
        airport_code="VIE",
        aliases=("vienna", "wien"),
        flight_base_eur=190.0,
        food_per_day_eur=45.0,
        local_transport_per_day_eur=6.0,
        climate=(
            ClimateMonth(3, -2, 42), ClimateMonth(6, -1, 40),
            ClimateMonth(11, 3, 40), ClimateMonth(17, 7, 38),
            ClimateMonth(21, 11, 45), ClimateMonth(25, 15, 48),
            ClimateMonth(27, 17, 45), ClimateMonth(27, 17, 42),
            ClimateMonth(22, 13, 42), ClimateMonth(15, 8, 42),
            ClimateMonth(8, 3, 48), ClimateMonth(4, 0, 48),
        ),
        hotels=(
            HotelSeed("Prater Budget Rooms", "budget", 62, 3.6, "Leopoldstadt"),
            HotelSeed("Ringstrasse Comfort Hotel", "midscale", 102, 4.2, "Innere Stadt"),
            HotelSeed("Kunsthaus Boutique Hotel", "boutique", 155, 4.6, "Museumsquartier"),
            HotelSeed("Grand Vienna Imperial", "upscale", 245, 4.8, "Innere Stadt"),
        ),
        attractions=(
            AttractionSeed(
                "Schönbrunn Palace & Gardens", "architecture",
                "Imperial palace with formal gardens and hilltop views.",
                3.5, 29.0, ("08:30", "17:30"), (), ("architecture", "history", "nature"),
                location="Hietzing",
            ),
            AttractionSeed(
                "Belvedere Museum", "museums",
                "Baroque palace housing Austrian art, including Klimt.",
                2.5, 18.0, ("09:00", "18:00"), (), ("museums", "art", "architecture"),
                location="Landstraße",
            ),
            AttractionSeed(
                "St. Stephen's Cathedral", "architecture",
                "Gothic cathedral in the heart of the old city.",
                1.0, 6.0, ("09:00", "17:00"), (), ("architecture", "history"),
                location="Innere Stadt",
            ),
            AttractionSeed(
                "Hofburg Palace", "history",
                "Former imperial residence with museums and state rooms.",
                2.5, 19.0, ("09:00", "17:30"), (), ("history", "architecture"),
                location="Innere Stadt",
            ),
            AttractionSeed(
                "Vienna State Opera Tour", "entertainment",
                "Backstage guided tour of the historic opera house.",
                1.0, 15.0, ("10:00", "16:00"), (), ("entertainment", "architecture"),
                location="Innere Stadt",
            ),
            AttractionSeed(
                "Prater & Giant Ferris Wheel", "entertainment",
                "Historic ferris wheel and a walk through the Prater park.",
                2.0, 14.0, ("10:00", "23:00"), (), ("entertainment", "nature"),
                location="Leopoldstadt",
            ),
            AttractionSeed(
                "Danube Island", "nature",
                "Long riverside park popular for walking and cycling.",
                2.0, 0.0, ("00:00", "23:59"), (), ("nature",),
                location="Donauinsel",
            ),
            AttractionSeed(
                "Kunsthistorisches Museum", "museums",
                "Fine-art museum with European masterpieces.",
                3.0, 21.0, ("10:00", "18:00"), (), ("museums", "art", "history"),
                location="Museumsquartier",
            ),
            AttractionSeed(
                "Veganista Ice Cream", "food",
                "Plant-based ice cream shop with changing flavours.",
                0.75, 6.0, ("11:00", "21:00"), (), ("food",),
                dietary_tags=("vegan", "vegetarian", "gluten_free"), meal_type="snack",
                location="Innere Stadt",
            ),
            AttractionSeed(
                "Café Harvest", "food",
                "Vegetarian café serving breakfast and light lunches.",
                1.5, 17.0, ("08:00", "19:00"), (), ("food",),
                dietary_tags=("vegetarian", "vegan"), meal_type="lunch",
                location="Neubau",
            ),
            AttractionSeed(
                "Naschmarkt Food Walk", "food",
                "Market visit with vegetarian tastings and local produce.",
                2.0, 25.0, ("09:00", "18:00"), (6,), ("food", "history"),
                dietary_tags=("vegetarian",), meal_type="lunch", location="Naschmarkt",
            ),
        ),
    ),
    "BARCELONA": CityProfile(
        key="barcelona",
        name="Barcelona",
        country="Spain",
        airport_code="BCN",
        aliases=("barcelona", "bcn"),
        flight_base_eur=200.0,
        food_per_day_eur=45.0,
        local_transport_per_day_eur=7.0,
        climate=(
            ClimateMonth(14, 6, 40), ClimateMonth(15, 7, 38),
            ClimateMonth(17, 9, 40), ClimateMonth(20, 11, 42),
            ClimateMonth(24, 15, 40), ClimateMonth(28, 19, 25),
            ClimateMonth(30, 22, 15), ClimateMonth(30, 22, 20),
            ClimateMonth(27, 19, 35), ClimateMonth(23, 15, 50),
            ClimateMonth(18, 10, 50), ClimateMonth(15, 7, 45),
        ),
        hotels=(
            HotelSeed("Gràcia Budget Rooms", "budget", 66, 3.6, "Gràcia"),
            HotelSeed("Eixample Comfort Hotel", "midscale", 104, 4.2, "Eixample"),
            HotelSeed("Gòtic Boutique Casa", "boutique", 158, 4.5, "Gothic Quarter"),
            HotelSeed("Grand Passeig Palace", "upscale", 235, 4.7, "Passeig de Gràcia"),
        ),
        attractions=(
            AttractionSeed(
                "Sagrada Família", "architecture",
                "Gaudí's unfinished basilica with remarkable interior light.",
                2.0, 26.0, ("09:00", "20:00"), (), ("architecture", "history"),
                location="Eixample",
            ),
            AttractionSeed(
                "Park Güell", "architecture",
                "Gaudí-designed park with mosaics and city views.",
                2.0, 18.0, ("09:30", "19:30"), (), ("architecture", "nature"),
                location="Gràcia",
            ),
            AttractionSeed(
                "Casa Batlló", "architecture",
                "Modernist townhouse with an imaginative interior.",
                1.5, 29.0, ("09:00", "20:00"), (), ("architecture", "art"),
                location="Passeig de Gràcia",
            ),
            AttractionSeed(
                "Picasso Museum", "museums",
                "Collection focused on Picasso's formative years.",
                2.0, 12.0, ("10:00", "19:00"), (0,), ("museums", "art"),
                location="El Born",
            ),
            AttractionSeed(
                "Gothic Quarter Walk", "history",
                "Self-guided walk through medieval streets and squares.",
                2.0, 0.0, ("09:00", "21:00"), (), ("history", "architecture"),
                location="Ciutat Vella",
            ),
            AttractionSeed(
                "Montjuïc Cable Car & Gardens", "nature",
                "Cable-car ride and garden walk above the harbour.",
                2.5, 14.0, ("10:00", "20:00"), (), ("nature", "entertainment"),
                location="Montjuïc",
            ),
            AttractionSeed(
                "Barceloneta Beach", "nature",
                "City beach for a relaxed walk or rest by the sea.",
                2.0, 0.0, ("00:00", "23:59"), (), ("nature",),
                location="Barceloneta",
            ),
            AttractionSeed(
                "Flamenco Show", "entertainment",
                "Small-venue flamenco performance (simulated programme).",
                1.5, 30.0, ("19:00", "23:00"), (), ("entertainment",),
                location="El Born",
            ),
            AttractionSeed(
                "La Boqueria Market", "food",
                "Historic market with fruit, snacks, and vegetarian options.",
                1.5, 15.0, ("08:00", "20:30"), (6,), ("food", "shopping"),
                dietary_tags=("vegetarian", "gluten_free"), meal_type="lunch",
                location="La Rambla",
            ),
            AttractionSeed(
                "Veggie Garden Barcelona", "food",
                "Plant-based restaurant with Catalan-inspired dishes.",
                1.5, 19.0, ("12:00", "23:00"), (), ("food",),
                dietary_tags=("vegan", "vegetarian", "gluten_free"), meal_type="dinner",
                location="Gràcia",
            ),
            AttractionSeed(
                "Vegetarian Tapas Tour", "food",
                "Evening tasting tour focused on vegetarian tapas.",
                2.5, 42.0, ("18:00", "22:30"), (), ("food", "history"),
                dietary_tags=("vegetarian", "vegan"), meal_type="dinner",
                location="El Born",
            ),
        ),
    ),
}

# Common aliases and spelling variants accepted by the mock tools.
INTEREST_ALIASES: dict[str, str] = {
    "art": "art",
    "arts": "art",
    "museum": "museums",
    "museums": "museums",
    "architecture": "architecture",
    "buildings": "architecture",
    "history": "history",
    "historic": "history",
    "nature": "nature",
    "parks": "nature",
    "outdoors": "nature",
    "food": "food",
    "foodie": "food",
    "gastronomy": "food",
    "restaurants": "food",
    "entertainment": "entertainment",
    "nightlife": "entertainment",
    "shows": "entertainment",
    "shopping": "shopping",
    "shops": "shopping",
    "photography": "architecture",
    "walks": "architecture",
    "walking": "architecture",
}

DIETARY_ALIASES: dict[str, str] = {
    "vegetarian": "vegetarian",
    "veggie": "vegetarian",
    "vegan": "vegan",
    "plant-based": "vegan",
    "plant based": "vegan",
    "gluten-free": "gluten_free",
    "gluten free": "gluten_free",
    "gluten_free": "gluten_free",
    "halal": "halal",
    "kosher": "kosher",
    "omnivore": "omnivore",
}


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold().strip()


_ALIAS_TO_CITY: dict[str, CityProfile] = {}
for _city in CITIES.values():
    _ALIAS_TO_CITY[_normalize_text(_city.name)] = _city
    _ALIAS_TO_CITY[_city.key] = _city
    for _alias in _city.aliases:
        _ALIAS_TO_CITY[_normalize_text(_alias)] = _city


def resolve_city(destination: str) -> CityProfile | None:
    """Resolve a city name or alias; return ``None`` when unsupported."""
    return _ALIAS_TO_CITY.get(_normalize_text(destination))


def supported_destination_names() -> list[str]:
    return [city.name for city in CITIES.values()]


_DEPARTURE_ALIAS_TO_CITY: dict[str, DepartureCity] = {}
for _departure in DEPARTURE_CITIES.values():
    _DEPARTURE_ALIAS_TO_CITY[_normalize_text(_departure.name)] = _departure
    _DEPARTURE_ALIAS_TO_CITY[_departure.key] = _departure
    for _alias in _departure.aliases:
        _DEPARTURE_ALIAS_TO_CITY[_normalize_text(_alias)] = _departure


def resolve_departure_city(departure_city: str) -> DepartureCity | None:
    """Resolve a supported departure city name or alias."""
    return _DEPARTURE_ALIAS_TO_CITY.get(_normalize_text(departure_city))


def supported_departure_names() -> list[str]:
    return [departure.name for departure in DEPARTURE_CITIES.values()]


def route_flight_minutes(
    departure: DepartureCity,
    destination: CityProfile,
) -> int:
    """Return the simulated one-way flight duration for a supported route."""
    return ROUTE_FLIGHT_MINUTES[(departure.key, destination.key)]


def normalize_interest(interest: str) -> str | None:
    return INTEREST_ALIASES.get(_normalize_text(interest))


def normalize_dietary_restriction(restriction: str) -> str | None:
    return DIETARY_ALIASES.get(_normalize_text(restriction))


def stable_fraction(*parts: object) -> float:
    """Return a deterministic value in [0, 1) derived from the arguments."""
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def season_factor(day: date) -> float:
    return SEASON_FACTORS[day.month]


def add_minutes(time_text: str, minutes: int) -> str:
    """Add minutes to an ``HH:MM`` clock time, wrapping at midnight."""
    hours, mins = (int(part) for part in time_text.split(":"))
    total = (hours * 60 + mins + minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def date_range(start: date, end: date) -> list[date]:
    """Inclusive date range helper used by the mock tools."""
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
