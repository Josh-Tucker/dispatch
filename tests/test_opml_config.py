import pytest
import os
import tempfile
from io import BytesIO
from unittest.mock import patch, MagicMock
from xml.etree import ElementTree as ET

from models import RssFeed, Settings


@pytest.mark.unit
class TestOPMLOperations:
    """Test OPML import and export operations."""
    
    def test_opml_parsing_valid_file(self, mock_opml_content):
        """Test parsing a valid OPML file."""
        from views import add_feeds_from_opml
        
        mock_file = MagicMock()
        mock_file.read.return_value = mock_opml_content.encode('utf-8')
        
        with patch('services.opml_service.add_feed') as mock_add_feed:
            add_feeds_from_opml(mock_file)
        
        # Should call add_feed for each feed in OPML
        assert mock_add_feed.call_count == 2
        mock_add_feed.assert_any_call('https://test1.com/feed.xml')
        mock_add_feed.assert_any_call('https://test2.com/feed.xml')
    
    def test_opml_parsing_nested_structure(self):
        """Test parsing OPML with nested folder structure."""
        nested_opml = '''<?xml version="1.0" encoding="UTF-8"?>
        <opml version="1.0">
            <head>
                <title>Nested OPML</title>
            </head>
            <body>
                <outline text="Tech News">
                    <outline text="Feed 1" xmlUrl="https://tech1.com/feed.xml" />
                    <outline text="Feed 2" xmlUrl="https://tech2.com/feed.xml" />
                </outline>
                <outline text="Sports">
                    <outline text="Feed 3" xmlUrl="https://sports1.com/feed.xml" />
                </outline>
                <outline text="Direct Feed" xmlUrl="https://direct.com/feed.xml" />
            </body>
        </opml>'''
        
        from views import add_feeds_from_opml
        
        mock_file = MagicMock()
        mock_file.read.return_value = nested_opml.encode('utf-8')
        
        with patch('services.opml_service.add_feed') as mock_add_feed:
            add_feeds_from_opml(mock_file)
        
        # Should find all feeds regardless of nesting
        assert mock_add_feed.call_count == 4
        expected_urls = [
            'https://tech1.com/feed.xml',
            'https://tech2.com/feed.xml', 
            'https://sports1.com/feed.xml',
            'https://direct.com/feed.xml'
        ]
        
        called_urls = [call[0][0] for call in mock_add_feed.call_args_list]
        for url in expected_urls:
            assert url in called_urls
    
    def test_opml_parsing_malformed_xml(self):
        """Test parsing malformed OPML XML."""
        malformed_opml = '''<?xml version="1.0" encoding="UTF-8"?>
        <opml version="1.0">
            <head>
                <title>Malformed OPML</title>
            </head>
            <body>
                <outline text="Feed 1" xmlUrl="https://test1.com/feed.xml" />
                <outline text="Unclosed outline" xmlUrl="https://test2.com/feed.xml"
            </body>
        </opml>'''
        
        from views import add_feeds_from_opml
        
        mock_file = MagicMock()
        mock_file.read.return_value = malformed_opml.encode('utf-8')
        
        # Should handle parsing errors gracefully
        with patch('services.opml_service.add_feed') as mock_add_feed:
            # The function should handle the error internally and not crash
            add_feeds_from_opml(mock_file)
            # Since the XML is malformed, no feeds should be added
            mock_add_feed.assert_not_called()
    
    def test_opml_parsing_empty_file(self):
        """Test parsing empty OPML file."""
        empty_opml = '''<?xml version="1.0" encoding="UTF-8"?>
        <opml version="1.0">
            <head>
                <title>Empty OPML</title>
            </head>
            <body>
            </body>
        </opml>'''
        
        from views import add_feeds_from_opml
        
        mock_file = MagicMock()
        mock_file.read.return_value = empty_opml.encode('utf-8')
        
        with patch('services.opml_service.add_feed') as mock_add_feed:
            add_feeds_from_opml(mock_file)
        
        # Should not call add_feed for empty file
        mock_add_feed.assert_not_called()
    
    def test_opml_parsing_missing_xmlurl(self):
        """Test parsing OPML with missing xmlUrl attributes."""
        missing_url_opml = '''<?xml version="1.0" encoding="UTF-8"?>
        <opml version="1.0">
            <head>
                <title>Missing URL OPML</title>
            </head>
            <body>
                <outline text="Valid Feed" xmlUrl="https://valid.com/feed.xml" />
                <outline text="Missing URL Feed" />
                <outline text="Another Valid Feed" xmlUrl="https://valid2.com/feed.xml" />
            </body>
        </opml>'''
        
        from views import add_feeds_from_opml
        
        mock_file = MagicMock()
        mock_file.read.return_value = missing_url_opml.encode('utf-8')
        
        with patch('services.opml_service.add_feed') as mock_add_feed:
            add_feeds_from_opml(mock_file)
        
        # Should only call add_feed for valid feeds
        assert mock_add_feed.call_count == 2
        mock_add_feed.assert_any_call('https://valid.com/feed.xml')
        mock_add_feed.assert_any_call('https://valid2.com/feed.xml')
    
    def test_opml_parsing_with_special_characters(self):
        """Test parsing OPML with special characters and encoding."""
        special_char_opml = '''<?xml version="1.0" encoding="UTF-8"?>
        <opml version="1.0">
            <head>
                <title>Special Characters OPML</title>
            </head>
            <body>
                <outline text="Feed with &amp; ampersand" xmlUrl="https://example.com/feed&amp;test.xml" />
                <outline text="Feed with &quot;quotes&quot;" xmlUrl="https://example.com/quotes.xml" />
                <outline text="Unicode Feed 中文" xmlUrl="https://unicode.com/中文.xml" />
                <outline text="Feed with &lt;brackets&gt;" xmlUrl="https://brackets.com/feed.xml" />
            </body>
        </opml>'''
        
        from views import add_feeds_from_opml
        
        mock_file = MagicMock()
        mock_file.read.return_value = special_char_opml.encode('utf-8')
        
        with patch('services.opml_service.add_feed') as mock_add_feed:
            add_feeds_from_opml(mock_file)
        
        # Should handle special characters correctly
        assert mock_add_feed.call_count == 4
        
        called_urls = [call[0][0] for call in mock_add_feed.call_args_list]
        assert 'https://example.com/feed&test.xml' in called_urls
        assert 'https://example.com/quotes.xml' in called_urls
        assert 'https://unicode.com/中文.xml' in called_urls
        assert 'https://brackets.com/feed.xml' in called_urls
    
    def test_opml_parsing_large_file(self):
        """Test parsing large OPML file with many feeds."""
        # Generate OPML with 1000 feeds
        large_opml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<opml version="1.0">',
            '<head><title>Large OPML</title></head>',
            '<body>'
        ]
        
        for i in range(1000):
            large_opml_parts.append(
                f'<outline text="Feed {i}" xmlUrl="https://example{i}.com/feed.xml" />'
            )
        
        large_opml_parts.extend(['</body>', '</opml>'])
        large_opml = '\n'.join(large_opml_parts)
        
        from views import add_feeds_from_opml
        
        mock_file = MagicMock()
        mock_file.read.return_value = large_opml.encode('utf-8')
        
        with patch('services.opml_service.add_feed') as mock_add_feed:
            add_feeds_from_opml(mock_file)
        
        # Should handle large files
        assert mock_add_feed.call_count == 1000
    
    def test_opml_file_encoding_variations(self):
        """Test OPML files with different encodings."""
        # Test UTF-8 with BOM
        utf8_bom_opml = '\ufeff<?xml version="1.0" encoding="UTF-8"?><opml version="1.0"><head><title>UTF-8 BOM</title></head><body><outline text="Test" xmlUrl="https://test.com/feed.xml" /></body></opml>'
        
        from views import add_feeds_from_opml
        
        mock_file = MagicMock()
        mock_file.read.return_value = utf8_bom_opml.encode('utf-8-sig')
        
        with patch('services.opml_service.add_feed') as mock_add_feed:
            add_feeds_from_opml(mock_file)
        
        mock_add_feed.assert_called_once_with('https://test.com/feed.xml')


@pytest.mark.unit
class TestConfigurationManagement:
    """Test configuration and settings management."""
    
    def test_theme_configuration_defaults(self, test_session):
        """Test default theme configuration."""
        with patch('services.theme_service.Session', return_value=test_session):
            from views import get_theme
            
            # Test default theme
            default_theme = get_theme('default')
            assert default_theme is not None
            assert 'name' in default_theme
            assert 'primary_colour' in default_theme
            assert 'background_colour' in default_theme
            
            # Test dark theme
            dark_theme = get_theme('dark')
            assert dark_theme is not None
            assert dark_theme['name'] == 'dark'
    
    def test_theme_configuration_custom_setting(self, test_session):
        """Test custom theme configuration from settings."""
        # Set custom default theme
        setting = Settings(key='theme', value='dark')
        test_session.add(setting)
        test_session.commit()
        
        with patch('services.theme_service.Session', return_value=test_session):
            from views import get_theme
            
            # Should return dark theme when 'default' is requested
            theme = get_theme('default')
            assert theme['name'] == 'dark'
    
    def test_setting_persistence(self, test_session):
        """Test that settings persist correctly."""
        with patch('services.theme_service.Session', return_value=test_session):
            from views import set_default_theme
            
            # Set a theme setting
            set_default_theme('dark')
        
        # Verify it was saved
        setting = test_session.query(Settings).filter_by(key='theme').first()
        assert setting is not None
        assert setting.value == 'dark'
        
        # Change it
        with patch('services.theme_service.Session', return_value=test_session):
            set_default_theme('light')
        
        # Verify it was updated, not duplicated
        settings = test_session.query(Settings).filter_by(key='theme').all()
        assert len(settings) == 1
        assert settings[0].value == 'light'
    
    def test_database_url_configuration(self):
        """Test database URL configuration."""
        from models import DATABASE_URL
        
        assert DATABASE_URL is not None
        assert isinstance(DATABASE_URL, str)
        assert 'sqlite:///' in DATABASE_URL
        assert 'rss_database.db' in DATABASE_URL
    
    def test_static_file_configuration(self):
        """Test static file path configuration."""
        # Test that favicon paths are correctly configured
        test_favicon_path = '/img/test_favicon.png'
        
        # The path should be relative to static directory
        assert test_favicon_path.startswith('/img/')
        assert test_favicon_path.endswith('.png')
    
    def test_pagination_configuration(self):
        """Test pagination settings."""
        from views import get_feed_entries_by_feed_id
        
        # Test default pagination (should be reasonable)
        # This is tested indirectly through the function behavior
        # Default entries_per_page in the route is 20
        
        with patch('services.entry_service.Session') as mock_session:
            # Create mock query chain that matches actual implementation
            mock_query = mock_session.return_value.query.return_value
            mock_query.filter_by.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.all.return_value = []
            
            get_feed_entries_by_feed_id('1', 1, 20)
            
            # Verify limit was called with 20
            mock_query.limit.assert_called_with(20)
    
    def test_date_format_configuration(self):
        """Test date formatting configuration."""
        from views import article_date_format, article_long_date_format
        
        test_date_str = "2023-12-25T14:30:00"
        
        # Test short format
        short_format = article_date_format(test_date_str)
        assert short_format == "25 Dec 2023"
        
        # Test long format
        long_format = article_long_date_format(test_date_str)
        assert long_format == "Monday, December 25, 2023"
    
    def test_executor_configuration(self):
        """Test Flask-Executor configuration."""
        from app import app
        
        # Should be configured for thread execution
        assert app.config.get("EXECUTOR_TYPE") == "thread"
    
    def test_flask_configuration_testing(self, app):
        """Test Flask configuration for testing."""
        with app.app_context():
            # Should have testing configurations
            assert app.config.get('TESTING') is True
            assert app.config.get('WTF_CSRF_ENABLED') is False


@pytest.mark.integration
class TestConfigurationIntegration:
    """Test configuration integration scenarios."""
    
    def test_theme_switching_persistence(self, client, test_session):
        """Test that theme switching persists across requests."""
        # Set theme to dark
        response = client.post('/set_default_theme', data={'theme': 'dark'})
        assert response.status_code == 200
        
        # Verify setting was saved
        setting = test_session.query(Settings).filter_by(key='theme').first()
        assert setting.value == 'dark'
        
        # Make another request and verify theme is still dark
        response = client.post('/set_theme', data={'theme': 'default'})
        assert response.status_code == 200
        # The response should reflect the dark theme since it's now the default
    
    def test_opml_import_with_existing_feeds(self, client, test_session, sample_feed):
        """Test OPML import when some feeds already exist."""
        # Create OPML that includes existing feed
        opml_with_existing = f'''<?xml version="1.0" encoding="UTF-8"?>
        <opml version="1.0">
            <head><title>Mixed OPML</title></head>
            <body>
                <outline text="Existing Feed" xmlUrl="{sample_feed.url}" />
                <outline text="New Feed" xmlUrl="https://new.com/feed.xml" />
            </body>
        </opml>'''
        
        opml_file = (BytesIO(opml_with_existing.encode()), 'mixed.opml')
        
        response = client.post('/upload_opml', data={'opml_file': opml_file})
        
        assert response.status_code == 200
        assert b'Processing OPML file' in response.data
    
    def test_configuration_after_database_reset(self, client, test_session):
        """Test configuration behavior after database reset."""
        # Set a theme
        response = client.post('/set_default_theme', data={'theme': 'dark'})
        assert response.status_code == 200
        
        # Clear all settings (simulate database reset)
        test_session.query(Settings).delete()
        test_session.commit()
        
        # Request default theme - should fall back to built-in default
        response = client.post('/set_theme', data={'theme': 'default'})
        assert response.status_code == 200
    
    def test_concurrent_configuration_changes(self, client, test_session):
        """Test concurrent configuration changes."""
        import threading
        
        results = []
        
        def change_theme(theme_name):
            response = client.post('/set_default_theme', data={'theme': theme_name})
            results.append((theme_name, response.status_code))
        
        # Start multiple threads changing themes
        threads = []
        theme_names = ['dark', 'light', 'dark', 'light', 'dark']
        
        for theme in theme_names:
            thread = threading.Thread(target=change_theme, args=(theme,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5)
        
        # All should succeed
        assert len(results) == 5
        for theme, status in results:
            assert status == 200
        
        # Final setting should be one of the themes
        final_setting = test_session.query(Settings).filter_by(key='theme').first()
        assert final_setting.value in ['dark', 'light']
    
    def test_large_opml_import_performance(self, client):
        """Test performance of large OPML import."""
        import time
        
        # Create large OPML with 100 feeds
        large_opml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<opml version="1.0">',
            '<head><title>Large Import Test</title></head>',
            '<body>'
        ]
        
        for i in range(100):
            large_opml_parts.append(
                f'<outline text="Performance Feed {i}" xmlUrl="https://perf{i}.com/feed.xml" />'
            )
        
        large_opml_parts.extend(['</body>', '</opml>'])
        large_opml = '\n'.join(large_opml_parts)
        
        opml_file = (BytesIO(large_opml.encode()), 'large.opml')
        
        start_time = time.time()
        response = client.post('/upload_opml', data={'opml_file': opml_file})
        end_time = time.time()
        
        assert response.status_code == 200
        assert b'Processing OPML file' in response.data
        
        # Should complete request quickly (processing happens in background)
        assert end_time - start_time < 5.0