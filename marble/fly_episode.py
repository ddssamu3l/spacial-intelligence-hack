"""Fly the rope-ascender policy through one built episode, headless.

    python -m marble.fly_episode built_worlds/<name> [--seconds 60] [--policy p.onnx]

The plant is `app.harness.marble_worlds.MarbleScene` -- the same scene the
web app serves -- driven by `chloe_policy.AscenderController` (Mrinal 2 by
default). The policy was NOT trained on real terrain or turning ropes; this
runner exists to measure what it does anyway.

Inputs  : built_worlds/<name>/ from marble.build_episode.
Outputs : stdout telemetry once per second (rope arc, goal distance,
          uprightness, hand-rope gap) and a verdict line: GOAL / FELL /
          TIMEOUT with meters of rope covered and height climbed.
"""

from __future__ import annotations

import argparse
import os

import numpy as np

from app.harness import chloe_policy
from app.harness.marble_worlds import DEFAULT_POLICY_RELATIVE_PATH, MarbleScene

GOAL_ARC_MARGIN_METERS = 0.30
FALLEN_UP_Z = 0.30


def fly(built_directory: str, seconds: float, policy_path: str | None) -> str:
    scene = MarbleScene(built_directory)
    controller = chloe_policy.AscenderController(
        scene.model, scene.default_joint_positions,
        policy_path=policy_path or os.path.join(
            chloe_policy.REPOSITORY_ROOT, DEFAULT_POLICY_RELATIVE_PATH))
    controller.go = True

    timestep = float(scene.model.opt.timestep)
    steps_per_second = int(round(1.0 / timestep))
    start_z = float(scene.data.qpos[2])
    goal_xy = np.asarray(scene.episode["goal"]["xy_meters"], dtype=float)

    def up_z() -> float:
        return float(np.asarray(scene.data.xmat[scene.pelvis_body_id])
                     .reshape(3, 3)[2, 2])

    def goal_distance() -> float:
        return float(np.linalg.norm(scene.data.qpos[0:2] - goal_xy))

    print("     t      arc     goal  pelvis_z   up_z  gap_cm")
    verdict = "TIMEOUT"
    for tick in range(int(seconds * steps_per_second)):
        controller.substep(scene.data)
        scene.step()
        arc = scene.ascender.slide_meters(scene.data)
        if tick % steps_per_second == 0:
            print(f"  {tick * timestep:4.0f}  {arc:7.2f}  {goal_distance():7.2f}"
                  f"  {scene.data.qpos[2]:8.3f}  {up_z():+.2f}"
                  f"  {scene.hand_rope_distance() * 100:6.2f}", flush=True)
        if up_z() < FALLEN_UP_Z:
            verdict = "FELL"
            break
        if arc >= scene.route.length - GOAL_ARC_MARGIN_METERS \
                and goal_distance() < scene.episode["goal"]["radius_meters"] + 1.0:
            verdict = "GOAL"
            break
    arc = scene.ascender.slide_meters(scene.data)
    climbed = float(scene.data.qpos[2]) - start_z
    print(f"[fly] {verdict}  rope {arc:.2f} / {scene.route.length:.2f} m"
          f"  climbed {climbed:+.2f} m  goal distance {goal_distance():.2f} m"
          f"  up_z {up_z():+.2f}", flush=True)
    return verdict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("built_directory")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--policy", default=None)
    arguments = parser.parse_args()
    fly(arguments.built_directory, arguments.seconds, arguments.policy)
