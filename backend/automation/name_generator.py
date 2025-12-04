"""
Name generator for Facebook Pages.
Generates names with 70% female and 30% male distribution.
"""

import random
from typing import List, Tuple

FEMALE_NAMES = [
    "Jane", "Sarah", "Emily", "Jessica", "Lily",
    "Emma", "Olivia", "Sophia", "Isabella", "Mia",
    "Charlotte", "Amelia", "Harper", "Evelyn", "Abigail",
    "Ella", "Avery", "Scarlett", "Grace", "Chloe",
    "Victoria", "Madison", "Luna", "Penelope", "Layla",
    "Riley", "Zoey", "Nora", "Hannah", "Aria",
]

MALE_NAMES = [
    "John", "James", "Michael", "David", "Robert",
    "William", "Richard", "Joseph", "Thomas", "Charles",
    "Daniel", "Matthew", "Anthony", "Mark", "Steven",
    "Andrew", "Joshua", "Kenneth", "Kevin", "Brian",
    "George", "Timothy", "Ronald", "Edward", "Jason",
    "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas",
]


def generate_page_names(base_name: str, count: int) -> List[Tuple[str, str]]:
    """
    Generate page names with 70% female and 30% male distribution.

    Args:
        base_name: The base name for pages (e.g., "Secure Auto Insurance")
        count: Number of page names to generate

    Returns:
        List of tuples: (full_page_name, gender)
        e.g., [("Secure Auto Insurance - Jane", "female"), ...]
    """
    female_count = int(count * 0.7)
    male_count = count - female_count

    # Select random names (with possible repetition if count > available names)
    female_selections = random.choices(FEMALE_NAMES, k=female_count)
    male_selections = random.choices(MALE_NAMES, k=male_count)

    # Create page names with gender tags
    page_names = []
    for name in female_selections:
        page_names.append((f"{base_name} - {name}", "female"))
    for name in male_selections:
        page_names.append((f"{base_name} - {name}", "male"))

    # Shuffle to mix genders randomly
    random.shuffle(page_names)

    return page_names


def get_page_name_for_sequence(base_name: str, sequence_num: int, total_count: int) -> Tuple[str, str]:
    """
    Get a deterministic page name for a specific sequence number.
    Uses the sequence number as seed for reproducibility.

    Args:
        base_name: The base name for the page
        sequence_num: The sequence number (1-indexed)
        total_count: Total number of pages being created

    Returns:
        Tuple of (page_name, gender)
    """
    # Calculate how many should be female up to this point
    female_threshold = 0.7

    # Use modular approach for deterministic gender assignment
    # Every 10 pages: 7 female, 3 male
    position_in_cycle = (sequence_num - 1) % 10
    is_female = position_in_cycle < 7

    # Seed random with sequence number for consistent name selection
    random.seed(sequence_num + hash(base_name))

    if is_female:
        name = random.choice(FEMALE_NAMES)
        gender = "female"
    else:
        name = random.choice(MALE_NAMES)
        gender = "male"

    # Reset random seed
    random.seed()

    return (f"{base_name} - {name}", gender)
