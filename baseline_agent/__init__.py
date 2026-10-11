"""The naive baseline agent for task T05. Python standard library only.

`recommend.recommend` is the way in: it builds the payload for one alert (`payload`), runs `agent.main` in the
guarded child process, where the one fixed prompt (`prompt`) is sent and the reply is checked (`reply`), and
returns ESCALATE with the SYSTEM_FAILURE flag for any fault.
"""
