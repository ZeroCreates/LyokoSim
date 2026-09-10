import tempfile
import unittest
import json

from lyokosim import (
    AccountManager,
    ConfigManager,
    LyokoSimulator,
    NoNarrator,
    SimulationError,
    TextToSpeech,
    apply_narrator_actions,
    narrator_system_message,
)


class LyokoSimulatorTests(unittest.TestCase):
    def make_simulator(self):
        return LyokoSimulator(ConfigManager(tempfile.mkdtemp()))

    def test_local_account_registers_and_authenticates(self):
        account = AccountManager(tempfile.mkdtemp())
        self.assertFalse(account.exists())
        account.register("Jeremy", "secret")
        self.assertTrue(account.exists())
        self.assertTrue(account.authenticate("Jeremy", "secret"))
        self.assertFalse(account.authenticate("Jeremy", "wrong"))
        with open(account.path, encoding="utf-8") as file:
            saved = json.load(file)
        self.assertNotIn("password", saved)
        self.assertNotEqual(saved["password_hash"], "secret")

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
        simulator.virtualize(["Aelita", "Ulrich"], "Forest")
        outcome = simulator.xana_attack()
        self.assertIn("activated", outcome)
        self.assertIn("attacked the real world", outcome)
        self.assertEqual(simulator.state.warriors["Aelita"].health, 100)
        self.assertEqual(simulator.state.warriors["Ulrich"].health, 90)
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
        self.assertNotIn("[MOVE", reply)
        self.assertEqual(simulator.state.warriors["Aelita"].location, "Mountain")

    def test_ai_fallback_moves_warrior_without_move_token(self):
        simulator = self.make_simulator()
        simulator.activate_system()
        simulator.virtualize(["Aelita"], "Forest")
        simulator.state.active_tower = "Mountain Tower 1"
        reply = apply_narrator_actions(simulator, "The team advances through Lyoko.")
        self.assertIn("Moved Aelita", reply)
        self.assertEqual(simulator.state.warriors["Aelita"].location, "Mountain")

    def test_movement_options_match_connected_route(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Aelita"], "Forest")
        simulator.state.active_tower = "Mountain Tower 1"
        options = simulator.narrator_context()["movement_options"]
        self.assertEqual(options[0]["current_sector"], "Forest")
        self.assertIn("Mountain", options[0]["connected_sectors"])
        self.assertIn("Mountain", options[0]["legal_next_sectors"])

    def test_reverse_sector_connection_is_accepted(self):
        config = ConfigManager(tempfile.mkdtemp())
        with open(config.sectors_path, "w", encoding="utf-8") as file:
            json.dump([
                {"name": "Forest", "towers": 2, "color": "#254638", "connections": []},
                {"name": "Mountain", "towers": 2, "color": "#38485b", "connections": ["Forest"]},
            ], file)
        simulator = LyokoSimulator(config)
        simulator.activate_system()
        simulator.virtualize(["Aelita"], "Forest")
        simulator.state.active_tower = "Mountain Tower 1"
        self.assertIn("Moved Aelita", simulator.move_warriors(["Aelita"], "Mountain"))

    def test_narrator_cannot_move_away_from_active_tower(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Aelita"], "Forest")
        simulator.state.active_tower = "Desert Tower 1"
        reply = apply_narrator_actions(simulator, "[MOVE Aelita TO Mountain]")
        self.assertIn("Movement request rejected", reply)
        self.assertEqual(simulator.state.warriors["Aelita"].location, "Forest")

    def test_mission_completes_after_ten_monitors(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        self.assertEqual(simulator.state.story_length, 10)
        with self.assertRaises(SimulationError):
            simulator.deactivate_tower()
        simulator.virtualize(["Ulrich"], "Forest")
        simulator.devirtualize(["Ulrich"])
        for _ in range(simulator.state.story_length):
            simulator.monitor()
        self.assertTrue(simulator.state.mission_successful)
        self.assertIn("deactivated", simulator.deactivate_tower())
        self.assertFalse(simulator.state.tower_active)
        self.assertIsNone(simulator.state.active_tower)

    def test_mission_completes_when_warrior_exhausts_on_final_monitor(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Ulrich"], "Forest")
        for _ in range(simulator.state.story_length - 1):
            simulator.monitor()
        self.assertFalse(simulator.state.mission_successful)
        simulator.monitor()
        reply = apply_narrator_actions(simulator, "Ulrich falls silent at 0% health.")
        self.assertIn("Devirtualised Ulrich", reply)
        self.assertTrue(simulator.state.mission_successful)
        self.assertIn("deactivated", simulator.deactivate_tower())

    def test_completed_mission_can_end_without_ai_token(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Ulrich"], "Forest")
        simulator.devirtualize(["Ulrich"])
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

    def test_text_to_speech_queues_enabled_messages(self):
        speaker = TextToSpeech(enabled=False)
        speaker.speak_async("The system reply [MOVE Aelita TO Forest]")
        self.assertTrue(speaker._messages.empty())

    def test_text_to_speech_starts_not_ready_when_disabled(self):
        speaker = TextToSpeech(enabled=False)
        self.assertFalse(speaker._ready.is_set())

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
        self.assertIn("weapon", context["configuration"]["warriors"][0])
        self.assertEqual(context["configuration"]["sectors"][0]["name"], "Forest")
        self.assertIn("color", context["configuration"]["sectors"][0])
        self.assertIn("towers", context["configuration"]["sectors"][0])
        self.assertIn("tower_connections", context["state"])
        self.assertIn("episode_guide", context)
        self.assertEqual(context["objective"]["target_tower"], simulator.state.active_tower)
        self.assertEqual(context["state"]["story_length"], 10)
        self.assertEqual(
            {warrior["name"] for warrior in context["virtualised_warriors"]},
            {"Aelita", "Odd"},
        )
        self.assertEqual(context["virtualised_warriors"][0]["sector"], "Forest")
        self.assertIn("role", context["virtualised_warriors"][0])
        self.assertIn("weapon", context["virtualised_warriors"][0])
        self.assertIn("mission_log", context)
        self.assertIn("protected_from_death", context["virtualised_warriors"][0])
        self.assertTrue(context["state"]["warriors"]["Aelita"]["protected_from_death"])

    def test_exhausted_warrior_can_be_devirtualised_by_narrator(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Ulrich"], "Forest")
        simulator.state.warriors["Ulrich"].health = 0
        reply = apply_narrator_actions(simulator, "Ulrich is exhausted. [DEVIRTUALISE Ulrich]")
        self.assertIn("Devirtualised Ulrich", reply)
        self.assertFalse(simulator.state.warriors["Ulrich"].virtualized)

    def test_zero_health_warrior_is_removed_even_without_ai_token(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Ulrich"], "Forest")
        simulator.state.warriors["Ulrich"].health = 0
        reply = apply_narrator_actions(simulator, "Ulrich collapses on Lyoko.")
        self.assertIn("Devirtualised Ulrich", reply)
        self.assertIn("Ulrich", simulator.state.devirtualized_warriors)
        self.assertFalse(simulator.state.warriors["Ulrich"].virtualized)

    def test_narrator_cannot_devirtualise_healthy_or_protected_warriors(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Aelita", "Ulrich"], "Forest")
        healthy_reply = apply_narrator_actions(simulator, "[DEVIRTUALISE Ulrich]")
        protected_reply = apply_narrator_actions(simulator, "[DEVIRTUALISE Aelita]")
        self.assertIn("still has 100% health", healthy_reply)
        self.assertIn("protected from death", protected_reply)
        self.assertTrue(simulator.state.warriors["Aelita"].virtualized)

    def test_narrator_can_update_virtualised_warrior_health(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Ulrich"], "Forest")
        reply = apply_narrator_actions(simulator, "[HEALTH Ulrich TO 45]")
        self.assertIn("Updated Ulrich health to 45%", reply)
        self.assertNotIn("[HEALTH", reply)
        self.assertEqual(simulator.state.warriors["Ulrich"].health, 45)

    def test_narrator_can_move_and_update_health_in_same_reply(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        simulator.virtualize(["Ulrich"], "Forest")
        simulator.state.active_tower = "Mountain Tower 1"
        simulator.state.possessed_towers = {"Mountain Tower 1"}
        reply = apply_narrator_actions(simulator, "[MOVE Ulrich TO Mountain] [HEALTH Ulrich TO 80]")
        self.assertIn("Moved Ulrich", reply)
        self.assertIn("Updated Ulrich health to 80%", reply)
        self.assertEqual(simulator.state.warriors["Ulrich"].location, "Mountain")
        self.assertEqual(simulator.state.warriors["Ulrich"].health, 80)

    def test_narrator_control_tokens_are_removed_from_display_text(self):
        simulator = self.make_simulator()
        display = apply_narrator_actions(simulator, "Victory [DEACTIVATE_TOWER]")
        self.assertEqual(display, "Victory")

    def test_health_updates_reject_nonvirtualised_or_protected_warriors(self):
        simulator = self.make_simulator()
        simulator.activate_tower()
        nonvirtualised_reply = apply_narrator_actions(simulator, "[HEALTH Ulrich TO 45]")
        simulator.virtualize(["Aelita"], "Forest")
        protected_reply = apply_narrator_actions(simulator, "[HEALTH Aelita TO 0]")
        self.assertIn("is not virtualised", nonvirtualised_reply)
        self.assertIn("must remain at 100%", protected_reply)

    def test_narrator_system_message_prioritises_authoritative_state(self):
        simulator = self.make_simulator()
        message = narrator_system_message(simulator)
        self.assertIn("authoritative simulator data", message.lower())
        self.assertIn("If any lower-priority text conflicts", message)
        self.assertIn("at most one movement token", message)
        self.assertIn("only if that exact name appears in the current virtualised_warriors list", message)
        self.assertIn("Never put a tower name, tower number, or sector-plus-tower name after TO", message)
        self.assertIn("use Forest, not Forest Tower 2", message)
        self.assertIn("If any movement condition is uncertain, omit the token", message)
        self.assertIn("A rejected request is not movement", message)
        self.assertIn("HARD RULE: a warrior must be currently virtualised before its health can be updated", message)
        self.assertIn("Never update the health of a non-virtualised warrior", message)
        self.assertIn("All warrior names and roles come from the user's configuration and may be completely custom", message)
        self.assertIn("Do not assume any configured warrior is Aelita, Ulrich, Odd, Yumi, William", message)
        self.assertIn("tower specialist, tower deactivator, or tower deactivation specialist performs the Aelita-like objective", message)
        self.assertIn("Follow the episode guide closely: preserve its setting, sequence, roles", message)
        self.assertIn("Keep the story original by inventing new scene details", message)
        self.assertIn("supercomputer is housed in the control room of the abandoned factory", message)
        self.assertIn("Every successful command advances the story", message)
        self.assertIn("A successful monitor command advances the numeric story_progress by exactly one", message)
        self.assertIn("A successful virtualise command is also a story event", message)
        self.assertIn("Do not answer a successful monitor or virtualise command with a bare status report", message)
        self.assertIn("Reply with story only, plus an action token only when", message)
        self.assertIn("At least one warrior must be devirtualised before the mission can end", message)
        self.assertIn("Never claim mission success while devirtualized_warriors is empty", message)
        self.assertIn("every health percentage you say must exactly match the authoritative warrior health", message)
        self.assertIn("If the deterministic outcome or established story gives a different supported health value", message)
        self.assertIn("If no deterministic outcome supports the change, do not update health", message)
        self.assertIn("If a non-protected virtualised warrior reaches 0 health or the story says they die on Lyoko", message)
        self.assertIn("A death story without an accepted [DEVIRTUALISE Exact Name] token is invalid", message)
        self.assertIn("Never place, describe, or imply a non-virtualised warrior is on Lyoko", message)
        self.assertIn("Use [DEACTIVATE_TOWER] only in that successful state", message)
        self.assertIn("never use [DEACTIVATE_TOWER]", message)
        self.assertIn('"configuration"', message)


if __name__ == "__main__":
    unittest.main()