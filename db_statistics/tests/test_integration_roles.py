from db_statistics.tests.pg_base import ROLE_GROUP, PostgresTestCase


class RolesIntegrationTests(PostgresTestCase):
    def test_users_list_contains_superuser_and_summary(self):
        data = self.post_json("/users/list/").json()

        self.assertTrue(data["ok"])
        names = {role["name"] for role in data["roles"]}
        self.assertIn(self.target["user"], names)
        self.assertGreaterEqual(data["summary"]["superuser_count"], 1)
        self.assertEqual(set(data["roles"][0]), {"name", "superuser", "createdb", "createrole", "inherit", "replication", "connection_limit", "valid_until", "member_count"})

    def test_users_list_search_excludes_group_roles(self):
        data = self.post_json("/users/list/", {"search": ROLE_GROUP}).json()

        self.assertEqual(data["total_count"], 0)

    def test_groups_list_contains_nologin_role(self):
        data = self.post_json("/groups/list/", {"search": ROLE_GROUP}).json()

        self.assertTrue(data["ok"])
        self.assertEqual([role["name"] for role in data["roles"]], [ROLE_GROUP])
        self.assertEqual(data["roles"][0]["valid_until"], "Бессрочно")

    def test_roles_list_unknown_sort_is_ignored(self):
        response = self.post_json("/users/list/", {"sort": "name; DROP ROLE x"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
