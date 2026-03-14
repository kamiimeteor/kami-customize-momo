import asyncio
import sys
from pathlib import Path

from droidrun.agent.oneflows.app_starter_workflow import AppStarter
from droidrun.agent.utils.llm_loader import load_agent_llms
from droidrun.config_manager import ConfigLoader
from droidrun.tools.driver.android import AndroidDriver

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


async def main(app_description: str) -> int:
    config = ConfigLoader.load(str(CONFIG_PATH))
    llms = load_agent_llms(config)
    app_opener_llm = llms["app_opener"]

    driver = AndroidDriver(
        serial=config.device.serial,
        use_tcp=config.device.use_tcp,
    )
    await driver.connect()

    workflow = AppStarter(
        tools=driver,
        llm=app_opener_llm,
        timeout=60,
        stream=config.agent.streaming,
        verbose=False,
    )
    result = await workflow.run(app_description=app_description)
    print(result)

    if isinstance(result, str) and "could not open app" in result.lower():
        return 1
    return 0


if __name__ == "__main__":
    description = " ".join(sys.argv[1:]).strip()
    if not description:
        raise SystemExit("Usage: python droidrun_open_app.py <app description>")
    raise SystemExit(asyncio.run(main(description)))
