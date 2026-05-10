import sys, os, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from database import init_db
    init_db()
    logger.info("Databas initierad OK")
except Exception as e:
    logger.error(f"init_db misslyckades: {e}", exc_info=True)
    raise  # Krascha så Railway visar felet i loggen

from app import app

if __name__ == '__main__':
    app.run()
