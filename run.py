from dotenv import load_dotenv

load_dotenv()

from core.pipeline import DatasetPipeline
from configs.settings import SANTE_CONFIG


if __name__ == "__main__":
    config = SANTE_CONFIG

    pipeline = DatasetPipeline(config)
    result = pipeline.run()

    if result:
        print(f"\nTon dataset est pret : {result}")
    else:
        print("\nLe pipeline a echoue. Consultez data/runs/ pour manifest.json et rejected.json.")
