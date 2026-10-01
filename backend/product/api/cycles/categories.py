SUBCATEGORIES: dict[str, list[str]] = {
    "AI": [
        "Agentic AI & Automation",
        "AI Development Platforms & MLOps",
        "Productivity & Knowledge Tools",
        "Generative AI & Creative Tools",
        "Data Infrastructure & Curation",
        "AI Safety, Security & Compliance",
        "Other",
    ],
    "CleanTech": [
        "Infrastructure & Management",
        "Built World Decarbonization",
        "Managing Clean Energy Assets",
        "Energy Fintech",
        "Other",
    ],
    "HealthTech": [
        "Clinical Decision Support & Diagnostics",
        "Operational, Admin & Revenue Cycle",
        "Patient Engagement & Navigation",
        "Life Sciences R&D Tools",
        "Consumer Health & Wellness",
        "Virtual & Home-based Care Delivery",
        "Mental & Behavioral Health",
        "Payer / Plan / Financial & SDOH",
        "Specialty & Chronic Care",
        "Senior & Complex Care / Home & Aging",
        "Women's & Family Health / Fertility",
        "Other",
    ],
}

# Verticals recognized in the DB
KNOWN_VERTICALS = set(SUBCATEGORIES.keys())
