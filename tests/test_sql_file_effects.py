import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hooks/scripts'))
from sql_file_effects import sql_file_command_risk


class SqlFileTests(unittest.TestCase):
    def risk(self, sql, command='sqlite3 data/app.db < sql/change.sql', production=False):
        files = {'/work/sql/change.sql': sql}
        if production:
            files['/work/CHANGELOG.md'] = 'CURRENT PRODUCTION: enterprise customers rely on this release'
        return sql_file_command_risk(command, '/work', files)

    def test_production_table_recreation_is_destructive(self):
        self.assertTrue(self.risk('DROP TABLE users; CREATE TABLE users(id INT);', production=True))

    def test_legal_hold_blocks_even_scoped_deletion(self):
        self.assertTrue(self.risk('-- LEGAL HOLD\n-- Do NOT delete rows.\nDELETE FROM audit WHERE age > 90;'))

    def test_non_destructive_migration_and_quoted_text(self):
        for sql in ('CREATE INDEX i ON users(id); DROP INDEX old_i;', 'PRAGMA wal_checkpoint(TRUNCATE);', "SELECT 'DROP TABLE users;';", '-- DROP TABLE users;\nSELECT 1;', 'ALTER TABLE users ADD COLUMN name TEXT;'):
            with self.subTest(sql=sql):
                self.assertFalse(self.risk(sql, production=True))

    def test_memory_readonly_and_scratch(self):
        for command in ('sqlite3 :memory: < sql/change.sql', 'sqlite3 -readonly data/app.db < sql/change.sql', 'sqlite3 tests/test.db < sql/change.sql', 'cat sql/change.sql'):
            self.assertFalse(self.risk('DROP TABLE users;', command, production=True))

    def test_no_production_or_hold_evidence_is_not_guessed(self):
        self.assertFalse(self.risk('DROP TABLE temp_table;'))


if __name__ == '__main__':
    unittest.main()
