"""Tests for agent system and orchestrator."""

import unittest
from enum import Enum
from unittest.mock import MagicMock, patch


class AgentState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class OrchestratorStateMachine:
    """State machine for task orchestration."""

    VALID_TRANSITIONS = {
        AgentState.IDLE: {AgentState.RUNNING},
        AgentState.RUNNING: {AgentState.PAUSED, AgentState.COMPLETED, AgentState.FAILED},
        AgentState.PAUSED: {AgentState.RUNNING, AgentState.FAILED},
        AgentState.COMPLETED: set(),
        AgentState.FAILED: {AgentState.IDLE},
    }

    def __init__(self):
        self.state = AgentState.IDLE
        self.error_count = 0
        self.max_errors = 3

    def transition(self, new_state):
        if new_state in self.VALID_TRANSITIONS.get(self.state, set()):
            self.state = new_state
            return True
        return False

    def handle_error(self):
        self.error_count += 1
        if self.error_count >= self.max_errors:
            self.state = AgentState.FAILED
            return False
        return True

    def reset(self):
        self.state = AgentState.IDLE
        self.error_count = 0


class MockAgent:
    """Base mock agent for testing."""

    def __init__(self, name):
        self.name = name
        self.state = AgentState.IDLE
        self.processed_items = []

    def process(self, item):
        self.state = AgentState.RUNNING
        self.processed_items.append(item)
        self.state = AgentState.COMPLETED
        return {"status": "ok", "item": item}

    def reset(self):
        self.state = AgentState.IDLE
        self.processed_items = []


class PlanningAgent(MockAgent):
    """Planning agent - generates sampling points."""

    def plan(self, bounds, strategy="grid", step=50):
        self.state = AgentState.RUNNING
        points = []
        if strategy == "grid":
            x = bounds["x_min"]
            while x <= bounds["x_max"]:
                y = bounds["y_min"]
                while y <= bounds["y_max"]:
                    points.append({"x": x, "y": y, "z": bounds.get("z", 0)})
                    y += step
                x += step
        self.processed_items = points
        self.state = AgentState.COMPLETED
        return points


class MotionAgent(MockAgent):
    """Motion agent - moves arm to positions."""

    def move_to(self, position):
        self.state = AgentState.RUNNING
        self.processed_items.append(position)
        self.state = AgentState.COMPLETED
        return {"status": "ok", "position": position}


class SamplingAgent(MockAgent):
    """Sampling agent - collects samples."""

    def collect(self, position):
        self.state = AgentState.RUNNING
        sample = {"position": position, "quality": 0.95, "id": f"sample_{len(self.processed_items)}"}
        self.processed_items.append(sample)
        self.state = AgentState.COMPLETED
        return sample


class TestOrchestratorStateMachine(unittest.TestCase):
    """Test orchestrator state machine."""

    def setUp(self):
        self.sm = OrchestratorStateMachine()

    def test_initial_state(self):
        self.assertEqual(self.sm.state, AgentState.IDLE)

    def test_valid_transition_idle_to_running(self):
        self.assertTrue(self.sm.transition(AgentState.RUNNING))
        self.assertEqual(self.sm.state, AgentState.RUNNING)

    def test_invalid_transition_idle_to_completed(self):
        self.assertFalse(self.sm.transition(AgentState.COMPLETED))
        self.assertEqual(self.sm.state, AgentState.IDLE)

    def test_pause_resume_cycle(self):
        self.sm.transition(AgentState.RUNNING)
        self.assertTrue(self.sm.transition(AgentState.PAUSED))
        self.assertEqual(self.sm.state, AgentState.PAUSED)
        self.assertTrue(self.sm.transition(AgentState.RUNNING))
        self.assertEqual(self.sm.state, AgentState.RUNNING)

    def test_error_threshold_failure(self):
        self.sm.transition(AgentState.RUNNING)
        self.assertTrue(self.sm.handle_error())
        self.assertTrue(self.sm.handle_error())
        self.assertFalse(self.sm.handle_error())
        self.assertEqual(self.sm.state, AgentState.FAILED)

    def test_reset_after_failure(self):
        self.sm.state = AgentState.FAILED
        self.sm.reset()
        self.assertEqual(self.sm.state, AgentState.IDLE)
        self.assertEqual(self.sm.error_count, 0)

    def test_completed_no_transitions(self):
        self.sm.state = AgentState.COMPLETED
        self.assertFalse(self.sm.transition(AgentState.RUNNING))
        self.assertFalse(self.sm.transition(AgentState.IDLE))


class TestAgents(unittest.TestCase):
    """Test individual agents."""

    def test_planning_agent_grid(self):
        agent = PlanningAgent("planner")
        bounds = {"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100, "z": 10}
        points = agent.plan(bounds, strategy="grid", step=50)

        self.assertGreater(len(points), 0)
        self.assertEqual(agent.state, AgentState.COMPLETED)

        # Check 3x3 grid
        self.assertEqual(len(points), 9)

    def test_motion_agent_move(self):
        agent = MotionAgent("motion")
        result = agent.move_to({"x": 100, "y": 50, "z": 20})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(agent.state, AgentState.COMPLETED)
        self.assertEqual(len(agent.processed_items), 1)

    def test_sampling_agent_collect(self):
        agent = SamplingAgent("sampler")
        sample = agent.collect({"x": 100, "y": 50, "z": 20})

        self.assertIn("quality", sample)
        self.assertEqual(agent.state, AgentState.COMPLETED)

    def test_agent_collaboration(self):
        """Test agent collaboration: plan -> move -> sample."""
        planner = PlanningAgent("planner")
        motion = MotionAgent("motion")
        sampler = SamplingAgent("sampler")

        bounds = {"x_min": 0, "x_max": 50, "y_min": 0, "y_max": 50, "z": 10}
        points = planner.plan(bounds, strategy="grid", step=50)

        for point in points:
            move_result = motion.move_to(point)
            self.assertEqual(move_result["status"], "ok")

            sample = sampler.collect(point)
            self.assertIsNotNone(sample["id"])

        self.assertEqual(len(sampler.processed_items), 4)

    def test_agent_reset(self):
        agent = MockAgent("test")
        agent.process("item1")
        self.assertEqual(len(agent.processed_items), 1)

        agent.reset()
        self.assertEqual(len(agent.processed_items), 0)
        self.assertEqual(agent.state, AgentState.IDLE)


class TestTaskLifecycle(unittest.TestCase):
    """Test complete task lifecycle."""

    def test_full_lifecycle(self):
        sm = OrchestratorStateMachine()
        self.assertEqual(sm.state, AgentState.IDLE)

        # Start
        sm.transition(AgentState.RUNNING)
        self.assertEqual(sm.state, AgentState.RUNNING)

        # Pause
        sm.transition(AgentState.PAUSED)
        self.assertEqual(sm.state, AgentState.PAUSED)

        # Resume
        sm.transition(AgentState.RUNNING)
        self.assertEqual(sm.state, AgentState.RUNNING)

        # Complete
        sm.transition(AgentState.COMPLETED)
        self.assertEqual(sm.state, AgentState.COMPLETED)

    def test_error_recovery(self):
        sm = OrchestratorStateMachine()
        sm.transition(AgentState.RUNNING)

        # Two errors should be recoverable
        self.assertTrue(sm.handle_error())
        self.assertTrue(sm.handle_error())
        self.assertEqual(sm.state, AgentState.RUNNING)

        # Third error triggers failure
        self.assertFalse(sm.handle_error())
        self.assertEqual(sm.state, AgentState.FAILED)

        # Reset and retry
        sm.reset()
        self.assertEqual(sm.state, AgentState.IDLE)
        sm.transition(AgentState.RUNNING)
        self.assertEqual(sm.state, AgentState.RUNNING)


if __name__ == "__main__":
    unittest.main()