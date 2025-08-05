
from models import Session, Settings


def get_theme(theme_name: str) -> str:
    """
    Get theme name, resolving 'default' to the stored preference.

    Args:
        theme_name: Name of the theme to retrieve ('default' checks database setting)

    Returns:
        str: Theme name to be used as CSS class
    """
    available_themes = get_available_themes()

    if theme_name == "default":
        session = Session()
        try:
            default_theme_name = Settings.get_setting(session, "theme")
            if default_theme_name and default_theme_name in available_themes:
                theme_name = default_theme_name
            else:
                theme_name = "light"
        finally:
            session.close()

    # Validate theme name
    if theme_name not in available_themes:
        theme_name = "light"

    return theme_name


def set_default_theme(theme_name: str) -> bool:
    """
    Set the default theme in the database.

    Args:
        theme_name: Name of the theme to set as default
    """
    available_themes = get_available_themes()

    # Validate theme name
    if theme_name not in available_themes:
        print(f"Invalid theme name: {theme_name}")
        return False

    session = Session()
    try:
        Settings.set_setting(session, "theme", theme_name)
        session.commit()
        print(f"Default theme set to: {theme_name}")
        return True
    except Exception as e:
        session.rollback()
        print(f"Error setting default theme: {e}")
        return False
    finally:
        session.close()


def get_default_theme() -> str:
    """
    Get the default theme name from the database.

    Returns:
        str: Default theme name
    """
    session = Session()
    try:
        theme_name = Settings.get_setting(session, "theme")
        if not theme_name or theme_name not in get_available_themes():
            theme_name = "light"
        return theme_name
    finally:
        session.close()


def get_available_themes() -> list[str]:
    """
    Get list of all available themes.

    Returns:
        list: List of theme names that correspond to CSS classes
    """
    return ["light", "dark", "clean", "new"]


def get_all_themes() -> list[dict[str, str]]:
    """
    Get all theme configurations with display names.

    Returns:
        list: List of theme dictionaries with name and display_name
    """
    return [
        {"name": "light", "display_name": "Light"},
        {"name": "dark", "display_name": "Dark"},
        {"name": "clean", "display_name": "Clean"},
        {"name": "new", "display_name": "New"},
    ]
