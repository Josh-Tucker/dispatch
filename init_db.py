from sqlalchemy import create_engine
from model import Base  
from views import add_feeds_from_opml, add_rss_entries_for_all_feeds

# Replace 'sqlite:///rss_database.db' with your desired database file path
engine = create_engine('sqlite:///rss_database.db')

# Create the database tables based on your models
Base.metadata.create_all(engine)

print("Database tables initialized.")

add_feeds_from_opml("subscriptions.opml")
add_rss_entries_for_all_feeds()
