"""Use frozen SABER tasks for judging the retained inference results."""
from pathlib import Path
import judge_osbench

judge_osbench.TASKS_DIR = Path(__file__).resolve().parent / 'tasks'
if __name__ == '__main__':
    judge_osbench.main()
