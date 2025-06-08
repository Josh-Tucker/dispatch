from models import Settings, Session


def get_theme(theme_name):
    """
    Get theme configuration by name.
    
    Args:
        theme_name: Name of the theme to retrieve ('default' checks database setting)
        
    Returns:
        dict: Theme configuration with colors and settings
    """
    themes = [
        {
            "name": "light",
            "primary_colour": "#f582ae",
            "text_colour": "#172c66",
            "highlight_colour": "#8bd3dd",
            "background_colour": "#fef6e4",
        },
        {
            "name": "dark",
            "primary_colour": "#f582ae",
            "text_colour": "#fef6e4",
            "highlight_colour": "#8bd3dd",
            "background_colour": "#172c66",
        },
        {
            "name": "clean",
            "primary_colour": "#000000",
            "text_colour": "#000000",
            "highlight_colour": "#ffffff",
            "background_colour": "#ffffff",
        },
        {
            "name": "new",
            "primary_colour": "#ff6b6b",
            "text_colour": "#2c3e50",
            "highlight_colour": "#4ecdc4",
            "background_colour": "#f8f9fa",
        },
    ]
    
    # Handle 'default' theme by checking database setting
    if theme_name == "default":
        session = Session()
        try:
            default_theme_name = Settings.get_setting(session, "theme")
            if default_theme_name:
                theme_name = default_theme_name
            else:
                theme_name = "light"  # Fallback to light if no setting
        finally:
            session.close()
    
    for theme in themes:
        if theme["name"] == theme_name:
            return theme
    
    # Default to light theme if not found
    return themes[0]


def set_default_theme(theme_name):
    """
    Set the default theme in the database.
    
    Args:
        theme_name: Name of the theme to set as default
    """
    session = Session()
    try:
        Settings.set_setting(session, "theme", theme_name)
        session.commit()
        print(f"Default theme set to: {theme_name}")
    except Exception as e:
        session.rollback()
        print(f"Error setting default theme: {e}")
    finally:
        session.close()


def get_default_theme():
    """
    Get the default theme from the database.
    
    Returns:
        dict: Default theme configuration
    """
    session = Session()
    try:
        theme_name = Settings.get_setting(session, "theme")
        if not theme_name:
            theme_name = "light"  # Default fallback
        return get_theme(theme_name)
    finally:
        session.close()


def get_available_themes():
    """
    Get list of all available themes.
    
    Returns:
        list: List of theme names
    """
    return ["light", "dark", "clean", "new"]


def get_all_themes():
    """
    Get all theme configurations.
    
    Returns:
        list: List of all theme dictionaries
    """
    return [
        {
            "name": "light",
            "primary_colour": "#f582ae",
            "text_colour": "#172c66",
            "highlight_colour": "#8bd3dd",
            "background_colour": "#fef6e4",
        },
        {
            "name": "dark",
            "primary_colour": "#f582ae",
            "text_colour": "#fef6e4",
            "highlight_colour": "#8bd3dd",
            "background_colour": "#172c66",
        },
        {
            "name": "clean",
            "primary_colour": "#000000",
            "text_colour": "#000000",
            "highlight_colour": "#ffffff",
            "background_colour": "#ffffff",
        },
        {
            "name": "new",
            "primary_colour": "#ff6b6b",
            "text_colour": "#2c3e50",
            "highlight_colour": "#4ecdc4",
            "background_colour": "#f8f9fa",
        },
    ]