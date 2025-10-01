from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import random
import logging
from pythonjsonlogger import jsonlogger
from datetime import datetime
import sqlite3
import os
from pydantic import BaseModel
from typing import Optional
import time

# Настройка JSON-логирования (stdout)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

for h in list(root_logger.handlers):
    root_logger.removeHandler(h)

stream_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
)
stream_handler.setFormatter(formatter)
root_logger.addHandler(stream_handler)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cat-O-Meter API",
    description="API для измерения котиковости 🐱",
    version="2.0.0"
)

# Prometheus /metrics
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
    )
    instrumentator.instrument(app)
except Exception as e:
    logger.warning(f"Prometheus instrumentation not enabled: {e}")

# Монтируем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели Pydantic
class CatRatingRequest(BaseModel):
    name: str

class CatRatingResponse(BaseModel):
    name: str
    percentage: int
    phrase: str
    emoji: str

class UserStats(BaseModel):
    user_id: str
    username: str
    total_checks: int
    avg_percentage: float
    max_percentage: int
    last_check: str

# Фразы для ответов
PHRASES = [
    "Мяу! Настоящий котик! 🐱",
    "В тебе есть кошачья душа! 😻",
    "Такой котик мог бы править миром! 👑",
    "Ты создан для мурлыканья! 💕",
    "Ого! Редкий котик! 🎯",
    "Почти идеальный котик! ✨",
    "Котик обнаружен! Мяу-мяу! 🐾",
    "Просто пушистый комок счастья! 🌟",
    "Настоящий охотник за мышкой! 🐭",
    "Мастер мурлыкания и лежания на клавиатуре! ⌨️"
]

# Глобальная переменная для статуса БД
db_initialized = False

def ensure_data_directory():
    """Убеждается, что папка для данных существует и доступна для записи"""
    try:
        data_path = '/app/data'
        if not os.path.exists(data_path):
            os.makedirs(data_path, exist_ok=True)
            logger.info(f"Created data directory: {data_path}")
        
        # Проверяем возможность записи
        test_file = os.path.join(data_path, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        
        return True
    except Exception as e:
        logger.error(f"Cannot create/write to data directory: {e}")
        return False

def get_db_connection():
    """Создание подключения к SQLite с обработкой ошибок"""
    try:
        if not ensure_data_directory():
            return None
            
        db_path = '/app/data/cat_meter.db'
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def init_db():
    """Инициализация базы данных с повторными попытками"""
    global db_initialized
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = get_db_connection()
            if conn is None:
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: No database connection")
                time.sleep(1)
                continue
                
            cursor = conn.cursor()
            
            # Создаем таблицы если их нет
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    username TEXT,
                    percentage INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    total_checks INTEGER DEFAULT 0,
                    avg_percentage REAL DEFAULT 0,
                    max_percentage INTEGER DEFAULT 0,
                    last_check TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            db_initialized = True
            logger.info("Database initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}/{max_retries}: Database initialization failed: {e}")
            time.sleep(1)
    
    logger.error("All database initialization attempts failed")
    return False

def safe_save_rating(user_id: str, username: str, percentage: int):
    """Безопасное сохранение рейтинга с обработкой ошибок БД"""
    if not db_initialized:
        # Пытаемся инициализировать БД при первой записи
        if not init_db():
            logger.warning("Database not available, skipping save")
            return False
    
    try:
        conn = get_db_connection()
        if conn is None:
            return False
            
        cursor = conn.cursor()
        
        # Сохраняем проверку
        cursor.execute('''
            INSERT INTO ratings (user_id, username, percentage)
            VALUES (?, ?, ?)
        ''', (user_id, username, percentage))
        
        # Обновляем статистику пользователя
        cursor.execute('''
            INSERT OR REPLACE INTO user_stats 
            (user_id, username, total_checks, avg_percentage, max_percentage, last_check)
            SELECT 
                ?,
                ?,
                COALESCE((SELECT total_checks + 1 FROM user_stats WHERE user_id = ?), 1),
                COALESCE((SELECT (avg_percentage * total_checks + ?) / (total_checks + 1) FROM user_stats WHERE user_id = ?), ?),
                COALESCE((SELECT MAX(max_percentage, ?) FROM user_stats WHERE user_id = ?), ?),
                CURRENT_TIMESTAMP
        ''', (user_id, username, user_id, percentage, user_id, percentage, percentage, user_id, percentage))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to save rating: {e}")
        return False

def calculate_cat_percentage(name: str) -> int:
    """Вычисляет процент котиковости на основе имени"""
    # Детерминированная, но псевдо-случайная логика
    seed = sum(ord(char) for char in name.lower()) + int(time.time())
    random.seed(seed)
    
    # Весовое распределение (чаще даем высокие проценты)
    rand = random.random()
    if rand < 0.05:  # 5% chance
        return random.randint(1, 20)
    elif rand < 0.15:  # 10% chance
        return random.randint(21, 50)
    elif rand < 0.4:  # 25% chance
        return random.randint(51, 75)
    elif rand < 0.8:  # 40% chance
        return random.randint(76, 95)
    else:  # 20% chance
        return random.randint(96, 100)

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске - без фатальных ошибок"""
    logger.info("Starting Cat-O-Meter API...")
    
    # Пытаемся инициализировать БД, но не падаем при ошибке
    if init_db():
        logger.info("API started with database support")
    else:
        logger.warning("API started in limited mode (no database)")

    # Регистрируем /metrics после старта
    try:
        if 'instrumentator' in globals():
            instrumentator.expose(app, include_in_schema=False)
            logger.info("Prometheus /metrics endpoint enabled")
    except Exception as e:
        logger.warning(f"Failed to expose /metrics: {e}")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Игровая главная страница"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/help-for-admin", response_class=HTMLResponse)
async def help_for_admin():
    """Страница помощи для администратора"""
    db_status = "✅ Available" if db_initialized else "❌ Limited mode"
    
    return f"""
    <html>
        <head>
            <title>Cat-O-Meter Admin Help</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
                .container {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); padding: 30px; border-radius: 20px; margin: 20px 0; }}
                h1 {{ text-align: center; font-size: 2.5em; margin-bottom: 30px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }}
                .endpoint {{ background: rgba(255,255,255,0.2); padding: 20px; margin: 15px 0; border-radius: 15px; border-left: 5px solid #ff6b6b; }}
                code {{ background: rgba(0,0,0,0.3); padding: 8px 12px; border-radius: 8px; font-family: 'Courier New', monospace; display: block; margin: 10px 0; }}
                .btn {{ display: inline-block; background: #ff6b6b; color: white; padding: 12px 25px; text-decoration: none; border-radius: 25px; margin: 10px 5px; transition: all 0.3s; }}
                .btn:hover {{ background: #ff5252; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(255,107,107,0.4); }}
                .status {{ background: rgba(255,255,255,0.2); padding: 15px; border-radius: 10px; margin: 20px 0; text-align: center; }}
                .nav {{ text-align: center; margin: 30px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🐱 Cat-O-Meter Admin Help</h1>
                
                <div class="status">
                    <strong>Database Status:</strong> {db_status}
                </div>
                
                <h2>📚 API Documentation</h2>
                
                <div class="endpoint">
                    <strong>GET /api/cat-meter/&#123;name&#125;</strong><br>
                    Check cat percentage by name<br>
                    <code>curl http://localhost:8000/api/cat-meter/Alexey</code>
                    <a href="/api/cat-meter/Test" class="btn">Test Now</a>
                </div>
                
                <div class="endpoint">
                    <strong>POST /api/cat-meter/</strong><br>
                    Check cat percentage with POST<br>
                    <code>curl -X POST -H "Content-Type: application/json" -d '&#123;"name":"Maria"&#125;' http://localhost:8000/api/cat-meter/</code>
                    <a href="/docs#/default/post_cat_meter_api_cat_meter__post" class="btn">Try in Swagger</a>
                </div>
                
                <div class="endpoint">
                    <strong>GET /api/stats/&#123;user_id&#125;</strong><br>
                    Get user statistics<br>
                    <code>curl http://localhost:8000/api/stats/user123</code>
                </div>
                
                <div class="endpoint">
                    <strong>GET /api/global-stats</strong><br>
                    Global service statistics<br>
                    <code>curl http://localhost:8000/api/global-stats</code>
                    <a href="/api/global-stats" class="btn">View Stats</a>
                </div>
                
                <div class="nav">
                    <a href="/" class="btn">🎮 Play Game</a>
                    <a href="/docs" class="btn">📖 Swagger Docs</a>
                    <a href="/redoc" class="btn">📚 ReDoc</a>
                    <a href="/health" class="btn">❤️ Health Check</a>
                </div>
            </div>
        </body>
    </html>
    """

@app.get("/api/cat-meter/{name}")
async def get_cat_meter(name: str):
    """GET endpoint для проверки котиковости"""
    if not name or len(name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    
    percentage = calculate_cat_percentage(name)
    phrase = random.choice(PHRASES)
    
    # Сохраняем в базу (если доступна)
    safe_save_rating(f"get_{name}", name, percentage)
    
    return CatRatingResponse(
        name=name,
        percentage=percentage,
        phrase=phrase,
        emoji="🐱"
    )

@app.post("/api/cat-meter/")
async def post_cat_meter(request_data: CatRatingRequest):
    """POST endpoint для проверки котиковости"""
    if not request_data.name or len(request_data.name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    
    percentage = calculate_cat_percentage(request_data.name)
    phrase = random.choice(PHRASES)
    
    # Сохраняем в базу (если доступна)
    safe_save_rating(f"post_{request_data.name}", request_data.name, percentage)
    
    return CatRatingResponse(
        name=request_data.name,
        percentage=percentage,
        phrase=phrase,
        emoji="🐱"
    )

@app.get("/api/stats/{user_id}")
async def get_user_stats(user_id: str):
    """Получить статистику пользователя"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")
    
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection failed")
    
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_stats WHERE user_id = ?', (user_id,))
        stats = cursor.fetchone()
        conn.close()
        
        if not stats:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserStats(
            user_id=stats['user_id'],
            username=stats['username'],
            total_checks=stats['total_checks'],
            avg_percentage=stats['avg_percentage'],
            max_percentage=stats['max_percentage'],
            last_check=stats['last_check']
        )
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/global-stats")
async def get_global_stats():
    """Глобальная статистика сервиса"""
    stats = {
        "total_checks": 0,
        "unique_users": 0,
        "average_percentage": 0,
        "database_available": db_initialized,
        "service_status": "running"
    }
    
    if db_initialized:
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) as total_checks FROM ratings')
                total_checks = cursor.fetchone()['total_checks']
                stats["total_checks"] = total_checks
                
                cursor.execute('SELECT COUNT(DISTINCT user_id) as unique_users FROM ratings')
                unique_users = cursor.fetchone()['unique_users']
                stats["unique_users"] = unique_users
                
                cursor.execute('SELECT AVG(percentage) as avg_percentage FROM ratings')
                avg_result = cursor.fetchone()['avg_percentage']
                stats["average_percentage"] = round(avg_result, 2) if avg_result else 0
                
                conn.close()
            except Exception as e:
                logger.error(f"Error getting global stats: {e}")
    
    return stats

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "available" if db_initialized else "unavailable",
        "version": "2.0.0"
    }
    return health_status

@app.get("/debug/db-status")
async def debug_db_status():
    """Endpoint для отладки статуса БД"""
    conn = get_db_connection()
    db_tables = []
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            db_tables = [table['name'] for table in tables]
            conn.close()
        except Exception as e:
            logger.error(f"Debug DB error: {e}")
    
    return {
        "db_initialized": db_initialized,
        "tables": db_tables,
        "data_directory_exists": os.path.exists('/app/data'),
        "data_directory_writable": ensure_data_directory()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
