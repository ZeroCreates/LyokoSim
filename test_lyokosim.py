import tempfile
import unittest
import json

from lyokosim import ConfigManager, LyokoSimulator, SimulationError, NoNarrator, TextToSpeech, apply_narrator_actions


class LyokoSimulatorTests(unittest.TestCase):
    def make_simulator(self):
        return LyokoSimulator(ConfigManager(tempfile.mkdtemp()))

    def test_warriors_need_an_active_tower(self):
        simulator = self.make_simulator()
        with self.assertRaises(SimulationError):
            simulator.virtualize(["Aelita"], "Forest")

    def test_full_mission_flow(self):
        simulator = self.make_simulator()
        self.assertIn("activated", simulator.activate_system())
        self.assertIn("Virtualised", simulator.virtualize(["Aelita", "Ulrich"], "Forest"))
        self.assertIn("Monitoring", simulator.monitor())
        self.assertIn("Devirtualised", simulator.devirtualize(["Aelita", "Ulrich"]))

    def test_commands_are_executed_by_the_operator(self):
        simulator = self.make_simulator()
        self.assertIn("activated", simulator.activate_tower())
        self.assertTrue(simulator.state.tower_active)

    def test_xana_damages_warriors_and_system(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Aelita"], "Forest")
        outcome = simulator.xana_attack()
        self.assertIn("activated", outcome)
        self.assertIn("attacked the real world", outcome)
        self.assertEqual(simulator.state.warriors["Aelita"].health, 100)
        self.assertEqual(simulator.state.system_integrity, 90)
        self.assertEqual(simulator.state.xana_attacks, 1)
        self.assertTrue(simulator.state.last_xana_event.endswith("."))
        self.assertEqual(len(simulator.state.possessed_towers), 1)
        self.assertEqual(simulator.state.active_tower, next(iter(simulator.state.possessed_towers)))
        first_tower = simulator.state.active_tower
        second_event = simulator.xana_attack()
        self.assertEqual(len(simulator.state.possessed_towers), 1)
        self.assertEqual(simulator.state.active_tower, first_tower)
        self.assertIn(first_tower, second_event)

    def test_xana_can_attack_without_virtualised_warriors(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        outcome = simulator.xana_attack()
        self.assertIn("activated", outcome)
        self.assertIn("attacked the real world", outcome)
        self.assertEqual(simulator.state.system_integrity, 90)

    def test_default_tower_counts_and_even_connections(self):
        simulator = self.make_simulator()
        tower_counts = {sector["name"]: sector["towers"] for sector in simulator.sector_configs}
        self.assertEqual(tower_counts["Forest"], 10)
        self.assertEqual(tower_counts["Mountain"], 10)
        self.assertEqual(tower_counts["Carith"], 1)
        links = simulator.tower_connections()
        self.assertIn("Forest Tower 2", links)
        self.assertIn("Forest Tower 10", links)
        self.assertNotIn("Forest Tower 1", links)
        self.assertNotIn("Carith Tower 1", links)
        self.assertEqual(simulator.sector_colors["Forest"], "#254638")

    def test_custom_sector_color_is_loaded_and_used_by_simulator(self):
        config = ConfigManager(tempfile.mkdtemp())
        with open(config.sectors_path, "w", encoding="utf-8") as file:
            json.dump([{"name": "Nebula", "towers": 2, "color": "#123ABC", "connections": []}], file)
        simulator = LyokoSimulator(config)
        self.assertEqual(simulator.sector_colors, {"Nebula": "#123ABC"})
        simulator.activate_tower()
        self.assertIn("Nebula", simulator.virtualize(["Aelita"], "Nebula"))

    def test_monitor_triggers_xana_attack(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Aelita"], "Forest")
        simulator.monitor()
        self.assertEqual(simulator.state.xana_attacks, 1)

    def test_narrator_can_move_warriors_toward_active_tower(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Aelita"], "Forest")
        simulator.state.active_tower = "Mountain Tower 1"
        simulator.state.possessed_towers = {"Mountain Tower 1"}
        reply = apply_narrator_actions(simulator, "The team advances. [MOVE Aelita TO Mountain]")
        self.assertIn("Moved Aelita", reply)
        self.assertEqual(simulator.state.warriors["Aelita"].location, "Mountain")

    def test_narrator_cannot_move_away_from_active_tower(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Aelita"], "Forest")
        simulator.state.active_tower = "Desert Tower 1"
        reply = apply_narrator_actions(simulator, "[MOVE Aelita TO Mountain]")
        self.assertIn("Movement request rejected", reply)
        self.assertEqual(simulator.state.warriors["Aelita"].location, "Forest")

    def test_mission_completes_after_three_to_five_monitors(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        self.assertGreaterEqual(simulator.state.story_length, 3)
        self.assertLessEqual(simulator.state.story_length, 5)
        with self.assertRaises(SimulationError):
            simulator.deactivate_tower()
        for _ in range(simulator.state.story_length):
            simulator.monitor()
        self.assertTrue(simulator.state.mission_successful)
        self.assertIn("deactivated", simulator.deactivate_tower())
        self.assertFalse(simulator.state.tower_active)
        self.assertIsNone(simulator.state.active_tower)

    def test_completed_mission_can_end_without_ai_token(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        for _ in range(simulator.state.story_length):
            simulator.monitor()
        self.assertTrue(simulator.state.mission_successful)
        self.assertTrue(simulator.state.tower_active)
        simulator.deactivate_tower()
        self.assertFalse(simulator.state.tower_active)

    def test_offline_narrator_is_available(self):
        simulator = self.make_simulator()
        narrator = NoNarrator()
        self.assertIn("No AI narrator", narrator.reply(simulator, "status", "ok"))

    def test_text_to_speech_can_be_disabled(self):
        speaker = TextToSpeech(enabled=False)
        speaker.speak_async("This should remain text only.")
        self.assertIsNone(speaker.error)

    def test_configuration_reload_updates_names_and_sectors(self):
        config = ConfigManager(tempfile.mkdtemp())
        simulator = LyokoSimulator(config)
        with open(config.warriors_path, "w", encoding="utf-8") as file:
            json.dump(["Lyoko", "Aelita"], file)
        with open(config.sectors_path, "w", encoding="utf-8") as file:
            json.dump(["Sector Alpha", "Sector Beta"], file)
        self.assertTrue(simulator.reload_config())
        self.assertEqual(simulator.warrior_names, ("Lyoko", "Aelita"))
        self.assertEqual(simulator.sectors, ("Sector Alpha", "Sector Beta"))

    def test_narrator_context_contains_all_configuration_and_mission_data(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Aelita", "Odd"], "Forest")
        context = simulator.narrator_context()
        self.assertEqual(context["configuration"]["warriors"][0]["name"], "Aelita")
        self.assertIn("role", context["configuration"]["warriors"][0])
        self.assertEqual(context["configuration"]["sectors"][0]["name"], "Forest")
        self.assertIn("color", context["configuration"]["sectors"][0])
        self.assertIn("towers", context["configuration"]["sectors"][0])
        self.assertIn("tower_connections", context["state"])
        self.assertIn("episode_guide", context)
        self.assertEqual(context["objective"]["target_tower"], simulator.state.active_tower)
        self.assertGreaterEqual(context["state"]["story_length"], 3)
        self.assertLessEqual(context["state"]["story_length"], 5)
        self.assertEqual(
            {warrior["name"] for warrior in context["virtualised_warriors"]},
            {"Aelita", "Odd"},
        )
        self.assertEqual(context["virtualised_warriors"][0]["sector"], "Forest")
        self.assertIn("role", context["virtualised_warriors"][0])
        self.assertIn("mission_log", context)


if __name__ == "__main__":
    unittest.main()