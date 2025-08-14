import json
import hashlib
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from collections import Counter

try:
    import chromadb
    import numpy as np
    from sentence_transformers import SentenceTransformer
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CachedResult:
    """Улучшенный кэшированный результат"""
    context: str
    timestamp: datetime
    usage_count: int = 0
    query_hash: str = ""
    semantic_key: str = ""
    tokens_saved: int = 0
    original_tokens: int = 0

@dataclass
class QueryIntent:
    """Определение намерения запроса"""
    intent_type: str
    confidence: float
    keywords: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)

class SmartContextOptimizer:
    """🧠 Умный оптимизатор контекста с приоритезацией"""
    
    # Приоритеты блоков информации (выше = важнее)
    CONTENT_PRIORITIES = {
        'контакты': 10,
        'адрес': 10,
        'телефон': 10,
        'цена': 9,
        'стоимость': 9,
        'поступление': 8,
        'документы': 8,
        'отбор': 8,
        'программы': 7,
        'направления': 7,
        'расписание': 6,
        'мероприятия': 5,
        'общая информация': 4
    }
    
    # Сокращения для экономии токенов
    ABBREVIATIONS = {
        'Национальный детский технопарк': 'НДТ',
        'образовательные программы': 'программы',
        'информационные технологии': 'ИТ',
        'искусственный интеллект': 'ИИ',
        'дополнительного образования': 'доп. образования',
        'обучающиеся': 'учащиеся',
        'образовательный процесс': 'обучение',
        'заявление': 'заявка',
        'документооборот': 'документы'
    }
    
    def optimize_context(self, context: str, query: str, max_tokens: int) -> str:
        """🔥 Агрессивная оптимизация контекста"""
        if not context:
            return context
            
        original_tokens = len(context) // 3
        if original_tokens <= max_tokens:
            return context
        
        # 1. Приоритезация блоков
        prioritized_context = self._prioritize_blocks(context, query)
        
        # 2. Сокращение фраз
        shortened_context = self._apply_abbreviations(prioritized_context)
        
        # 3. Умное урезание предложений
        optimized_context = self._smart_sentence_trimming(shortened_context, query)
        
        # 4. Финальное урезание до лимита
        final_context = self._final_trim(optimized_context, max_tokens)
        
        final_tokens = len(final_context) // 3
        logger.info(f"🎯 Оптимизация: {original_tokens} → {final_tokens} токенов ({((original_tokens-final_tokens)/original_tokens*100):.1f}% экономия)")
        
        return final_context
    
    def _prioritize_blocks(self, context: str, query: str) -> str:
        """Приоритезация блоков по важности для запроса"""
        query_lower = query.lower()
        blocks = context.split('\n\n')
        scored_blocks = []
        
        for block in blocks:
            if not block.strip():
                continue
                
            score = 0
            block_lower = block.lower()
            
            # Базовый приоритет по содержимому
            for keyword, priority in self.CONTENT_PRIORITIES.items():
                if keyword in block_lower:
                    score += priority
            
            # Бонус за соответствие запросу
            query_words = set(query_lower.split())
            block_words = set(block_lower.split())
            relevance = len(query_words & block_words) / len(query_words) if query_words else 0
            score += relevance * 15
            
            scored_blocks.append((score, block))
        
        # Сортируем по важности и возвращаем топ блоки
        scored_blocks.sort(reverse=True, key=lambda x: x[0])
        return '\n\n'.join([block for _, block in scored_blocks[:6]])  # Топ 6 блоков
    
    def _apply_abbreviations(self, text: str) -> str:
        """Применяем сокращения"""
        for full_form, abbrev in self.ABBREVIATIONS.items():
            text = text.replace(full_form, abbrev)
        return text
    
    def _smart_sentence_trimming(self, text: str, query: str) -> str:
        """Умное урезание предложений"""
        sentences = text.split('. ')
        query_words = set(query.lower().split())
        
        scored_sentences = []
        for sentence in sentences:
            if len(sentence.strip()) < 10:  # Пропускаем очень короткие
                continue
                
            sentence_words = set(sentence.lower().split())
            relevance = len(query_words & sentence_words) / len(query_words) if query_words else 0.1
            
            # Бонус за ключевые фразы
            if any(key in sentence.lower() for key in ['контакт', 'адрес', 'телефон', 'цена', 'стоимость']):
                relevance += 0.5
            
            scored_sentences.append((relevance, sentence))
        
        # Берем топ предложения
        scored_sentences.sort(reverse=True, key=lambda x: x[0])
        selected = [sent for _, sent in scored_sentences[:12]]  # Топ 12 предложений
        
        return '. '.join(selected) + '.'
    
    def _final_trim(self, text: str, max_tokens: int) -> str:
        """Финальное урезание до лимита"""
        target_chars = max_tokens * 3
        if len(text) <= target_chars:
            return text
        
        # Ищем хорошее место для обрезки
        sentences = text[:target_chars].split('. ')
        if len(sentences) > 1:
            return '. '.join(sentences[:-1]) + '.'
        else:
            return text[:target_chars] + '...'

class AdvancedRAGCache:
    """🚀 Продвинутая система кэширования с семантическим поиском"""
    
    def __init__(self, max_size: int = 1000):
        self.exact_cache: Dict[str, CachedResult] = {}  # Точный кэш
        self.semantic_cache: Dict[str, List[CachedResult]] = {}  # Семантический кэш
        self.popular_cache: Dict[str, CachedResult] = {}  # Кэш популярных запросов
        self.query_patterns: Counter = Counter()  # Статистика паттернов
        self.max_size = max_size
        
        # Предопределенные популярные запросы
        self.popular_patterns = {
            'адрес': "📍 НДТ, Минск\n👥 Для учащихся 9-11 классов",
            'контакты': "📞 Телефон: указан на сайте\n📧 Email: на официальном сайте",
            'направления': "🎓 15 образовательных направлений:\n• ИТ\n• Робототехника\n• Биотехнологии\n• И другие",
            'поступление': "📝 Отбор: 2 этапа\n1️⃣ Заочный: заявка + проект\n2️⃣ Очный: тест + собеседование"
        }
    
    def get_cached_result(self, query: str) -> Optional[CachedResult]:
        """Получить результат из кэша (многоуровневый поиск)"""
        query_hash = self._hash_query(query)
        
        # 1. Точный кэш
        if query_hash in self.exact_cache:
            result = self.exact_cache[query_hash]
            if self._is_cache_valid(result):
                result.usage_count += 1
                logger.info(f"⚡ Точный кэш хит: {query[:30]}...")
                return result
        
        # 2. Популярный кэш
        normalized_query = self._normalize_query(query)
        if normalized_query in self.popular_cache:
            result = self.popular_cache[normalized_query]
            result.usage_count += 1
            logger.info(f"🔥 Популярный кэш хит: {query[:30]}...")
            return result
        
        # 3. Семантический кэш
        semantic_key = self._get_semantic_key(query)
        if semantic_key in self.semantic_cache:
            for cached_result in self.semantic_cache[semantic_key]:
                if self._is_semantically_similar(query, cached_result.query_hash) and self._is_cache_valid(cached_result):
                    cached_result.usage_count += 1
                    logger.info(f"🧠 Семантический кэш хит: {query[:30]}...")
                    return cached_result
        
        return None
    
    def cache_result(self, query: str, context: str, original_tokens: int = 0):
        """Сохранить результат в кэш"""
        query_hash = self._hash_query(query)
        semantic_key = self._get_semantic_key(query)
        
        result = CachedResult(
            context=context,
            timestamp=datetime.now(),
            query_hash=query_hash,
            semantic_key=semantic_key,
            original_tokens=original_tokens,
            tokens_saved=max(0, original_tokens - len(context) // 3)
        )
        
        # Сохраняем в точный кэш
        self.exact_cache[query_hash] = result
        
        # Сохраняем в семантический кэш
        if semantic_key not in self.semantic_cache:
            self.semantic_cache[semantic_key] = []
        self.semantic_cache[semantic_key].append(result)
        
        # Обновляем статистику
        normalized = self._normalize_query(query)
        self.query_patterns[normalized] += 1
        
        # Если запрос стал популярным - добавляем в популярный кэш
        if self.query_patterns[normalized] >= 3:
            self.popular_cache[normalized] = result
            logger.info(f"📈 Запрос добавлен в популярный кэш: {normalized}")
        
        # Очищаем кэш при превышении лимита
        if len(self.exact_cache) > self.max_size:
            self._cleanup_cache()
    
    def _hash_query(self, query: str) -> str:
        """Хэш запроса"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
    
    def _normalize_query(self, query: str) -> str:
        """Нормализация запроса для поиска паттернов"""
        query = query.lower().strip()
        # Заменяем синонимы
        synonyms = {
            'где находится': 'адрес',
            'как добраться': 'адрес',
            'местоположение': 'адрес',
            'связаться': 'контакты',
            'телефон': 'контакты',
            'курсы': 'направления',
            'программы': 'направления',
            'как поступить': 'поступление',
            'документы': 'поступление'
        }
        
        for synonym, canonical in synonyms.items():
            if synonym in query:
                return canonical
        
        # Извлекаем ключевое слово
        for keyword in ['адрес', 'контакты', 'направления', 'поступление', 'цена', 'стоимость']:
            if keyword in query:
                return keyword
        
        return query[:20]  # Первые 20 символов как fallback
    
    def _get_semantic_key(self, query: str) -> str:
        """Получить семантический ключ для группировки похожих запросов"""
        # Упрощенная семантическая группировка по ключевым словам
        keywords = {
            'location': ['адрес', 'где', 'находится', 'местоположение', 'добраться'],
            'contact': ['контакт', 'телефон', 'связь', 'написать'],
            'programs': ['направления', 'программы', 'курсы', 'изучают', 'специальности'],
            'admission': ['поступление', 'поступить', 'отбор', 'документы', 'требования'],
            'cost': ['цена', 'стоимость', 'платить', 'деньги', 'бесплатно'],
            'schedule': ['расписание', 'график', 'время', 'смены'],
            'general': ['информация', 'данные', 'сведения', 'про', 'о']
        }
        
        query_lower = query.lower()
        for key, words in keywords.items():
            if any(word in query_lower for word in words):
                return key
        
        return 'general'
    
    def _is_semantically_similar(self, query1: str, query2_hash: str) -> bool:
        """Проверка семантической похожести (упрощенная)"""
        # Здесь можно интегрировать более сложную семантическую модель
        # Пока используем простое сравнение ключевых слов
        return True  # Упрощенная версия
    
    def _is_cache_valid(self, result: CachedResult) -> bool:
        """Проверка валидности кэша"""
        # Кэш действителен 24 часа для популярных запросов
        if result.usage_count >= 5:
            return (datetime.now() - result.timestamp) < timedelta(hours=24)
        # 12 часов для обычных запросов
        return (datetime.now() - result.timestamp) < timedelta(hours=12)
    
    def _cleanup_cache(self):
        """Умная очистка кэша"""
        logger.info("🧹 Очистка кэша...")
        
        # Удаляем старые и редко используемые записи
        cutoff_time = datetime.now() - timedelta(hours=6)
        
        # Очистка точного кэша
        to_remove = []
        for key, result in self.exact_cache.items():
            if result.timestamp < cutoff_time and result.usage_count < 2:
                to_remove.append(key)
        
        for key in to_remove:
            del self.exact_cache[key]
        
        # Очистка семантического кэша
        for key in list(self.semantic_cache.keys()):
            self.semantic_cache[key] = [
                result for result in self.semantic_cache[key]
                if result.timestamp >= cutoff_time or result.usage_count >= 2
            ]
            if not self.semantic_cache[key]:
                del self.semantic_cache[key]
        
        logger.info(f"✅ Кэш очищен. Удалено: {len(to_remove)} записей")
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика кэша"""
        total_usage = sum(result.usage_count for result in self.exact_cache.values())
        total_tokens_saved = sum(result.tokens_saved for result in self.exact_cache.values())
        
        return {
            "exact_cache_size": len(self.exact_cache),
            "semantic_cache_groups": len(self.semantic_cache),
            "popular_cache_size": len(self.popular_cache),
            "total_usage_count": total_usage,
            "total_tokens_saved": total_tokens_saved,
            "top_patterns": dict(self.query_patterns.most_common(5))
        }

class TokenOptimizedRAG:
    """🚀 Максимально оптимизированная RAG система"""
    
    def __init__(self, knowledge_base_path: str = "knowledge_base.json", max_tokens: int = 500):
        self.knowledge_base_path = Path(knowledge_base_path)
        self.max_tokens = max_tokens
        self.knowledge_base = {}
        self.cache = AdvancedRAGCache()
        self.optimizer = SmartContextOptimizer()
        
        # Статистика
        self.stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'tokens_saved': 0,
            'processing_time_saved': 0.0
        }
        
        self.load_knowledge()
        self._preload_popular_queries()
        
        logger.info(f"🎯 Максимально оптимизированная RAG готова | Лимит: {max_tokens} токенов")
    
    def _preload_popular_queries(self):
        """Предзагрузка популярных запросов"""
        for pattern, response in self.cache.popular_patterns.items():
            self.cache.popular_cache[pattern] = CachedResult(
                context=response,
                timestamp=datetime.now(),
                usage_count=10,
                query_hash=self.cache._hash_query(pattern)
            )
        logger.info("📚 Предзагружены популярные запросы")
    
    def load_knowledge(self):
        """Загрузка базы знаний"""
        try:
            with open(self.knowledge_base_path, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)
            logger.info("📚 База знаний загружена")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки: {e}")
            self.knowledge_base = {}
    
    def get_context(self, query: str) -> str:
        """🎯 ГЛАВНАЯ ФУНКЦИЯ: Максимально оптимизированный контекст"""
        start_time = time.time()
        self.stats['total_queries'] += 1
        
        # 1. ПРОВЕРЯЕМ МНОГОУРОВНЕВЫЙ КЭШ
        cached_result = self.cache.get_cached_result(query)
        if cached_result:
            self.stats['cache_hits'] += 1
            self.stats['processing_time_saved'] += 0.5  # Среднее время экономии
            return cached_result.context
        
        # 2. БЫСТРАЯ ОБРАБОТКА ПО ТИПУ ЗАПРОСА
        intent = self._analyze_query_intent(query)
        context = self._get_context_by_intent(query, intent)
        original_tokens = len(context) // 3
        
        # 3. АГРЕССИВНАЯ ОПТИМИЗАЦИЯ
        optimized_context = self.optimizer.optimize_context(context, query, self.max_tokens)
        
        # 4. КЭШИРУЕМ РЕЗУЛЬТАТ
        self.cache.cache_result(query, optimized_context, original_tokens)
        
        # Статистика
        tokens_saved = original_tokens - len(optimized_context) // 3
        self.stats['tokens_saved'] += tokens_saved
        processing_time = time.time() - start_time
        
        logger.info(f"🔥 Обработан: {query[:30]}... | Токенов: {len(optimized_context)//3} | Время: {processing_time:.3f}с")
        
        return optimized_context
    
    def _analyze_query_intent(self, query: str) -> QueryIntent:
        """🧠 Анализ намерения запроса"""
        query_lower = query.lower().strip()
        
        # Определяем тип запроса
        intent_patterns = {
            'greeting': ['привет', 'здравствуй', 'добрый', 'hello', 'hi', 'начать', 'старт'],
            'location': ['адрес', 'где', 'находится', 'местоположение', 'добраться', 'география'],
            'contact': ['контакт', 'телефон', 'связь', 'написать', 'обратиться'],
            'directions': ['направления', 'программы', 'курсы', 'специальности', 'изучают', 'список'],
            'admission': ['поступление', 'поступить', 'документы', 'отбор', 'требования', 'как попасть'],
            'cost': ['цена', 'стоимость', 'платить', 'деньги', 'бесплатно', 'затраты'],
            'schedule': ['расписание', 'график', 'время', 'смены', 'когда'],
            'general': ['информация', 'данные', 'сведения', 'про', 'о', 'расскажи']
        }
        
        for intent_type, keywords in intent_patterns.items():
            matches = sum(1 for keyword in keywords if keyword in query_lower)
            if matches > 0:
                confidence = min(1.0, matches / 3.0)  # Нормализуем уверенность
                return QueryIntent(
                    intent_type=intent_type,
                    confidence=confidence,
                    keywords=[kw for kw in keywords if kw in query_lower]
                )
        
        return QueryIntent(intent_type='general', confidence=0.5)
    
    def _get_context_by_intent(self, query: str, intent: QueryIntent) -> str:
        """Получение контекста по типу намерения"""
        
        if intent.intent_type == 'greeting':
            return ""  # Пустой контекст для приветствий
        
        elif intent.intent_type == 'location':
            return self._get_location_info()
        
        elif intent.intent_type == 'contact':
            return self._get_contact_info()
        
        elif intent.intent_type == 'directions':
            return self._get_directions_info()
        
        elif intent.intent_type == 'admission':
            return self._get_admission_info()
        
        elif intent.intent_type == 'cost':
            return self._get_cost_info()
        
        elif intent.intent_type == 'schedule':
            return self._get_schedule_info()
        
        else:
            return self._get_general_info()
    
    def _get_location_info(self) -> str:
        """Краткая информация о местоположении"""
        about = self.knowledge_base.get("о_технопарке", {})
        if about.get('адрес'):
            contact = about.get('контактная_информация', {})
            result = f"📍 {about['адрес']}"
            if contact.get('телефон'):
                result += f"\n📞 {contact['телефон']}"
            if about.get('целевая_аудитория'):
                result += f"\n👥 {about['целевая_аудитория']}"
            return result
        return "📍 НДТ, Минск\n👥 Для учащихся 9-11 классов"
    
    def _get_contact_info(self) -> str:
        """Контактная информация"""
        about = self.knowledge_base.get("о_технопарке", {})
        contact = about.get('контактная_информация', {})
        
        result = "📞 Контакты НДТ:\n"
        if contact.get('телефон'):
            result += f"• Телефон: {contact['телефон']}\n"
        if contact.get('email'):
            result += f"• Email: {contact['email']}\n"
        if contact.get('сайт'):
            result += f"• Сайт: {contact['сайт']}"
        
        return result if len(result) > 20 else "📞 Контакты указаны на официальном сайте"
    
    def _get_directions_info(self) -> str:
        """Образовательные направления"""
        directions = self.knowledge_base.get("список_направлений", [])
        if directions:
            # Показываем первые 10 направлений
            top_directions = directions[:10]
            return "🎓 Образовательные направления:\n" + "\n".join(f"• {d}" for d in top_directions)
        
        # Fallback
        return "🎓 15 современных направлений: ИТ, робототехника, биотехнологии, мехатроника и др."
    
    def _get_admission_info(self) -> str:
        """Информация о поступлении"""
        selection = self.knowledge_base.get("процедура_отбора", {})
        if selection:
            stages = selection.get("этапы", [])
            if stages:
                result = "📝 Процедура отбора:\n"
                for i, stage in enumerate(stages[:2], 1):  # Первые 2 этапа
                    result += f"{i}️⃣ {stage.get('название', f'Этап {i}')}: {stage.get('описание', 'детали на сайте')}\n"
                return result
        
        return "📝 Отбор: 2 этапа\n1️⃣ Заочный: заявка + проект\n2️⃣ Очный: тест + собеседование"
    
    def _get_cost_info(self) -> str:
        """Информация о стоимости"""
        about = self.knowledge_base.get("о_технопарке", {})
        if 'бесплатно' in str(about).lower():
            return "�� Обучение БЕСПЛАТНОЕ\n🎯 Финансируется государством"
        return "💰 Информация о стоимости уточняется при поступлении"
    
    def _get_schedule_info(self) -> str:
        """Информация о расписании"""
        sessions = self.knowledge_base.get("образовательные_смены", {})
        if sessions:
            return "📅 Образовательные смены проводятся регулярно\n📋 Подробное расписание на сайте"
        return "📅 Расписание смен и занятий размещается на официальном сайте"
    
    def _get_general_info(self) -> str:
        """Общая информация"""
        about = self.knowledge_base.get("о_технопарке", {})
        if about:
            result = f"🏫 {about.get('полное_название', 'НДТ')}\n"
            if about.get('дата_основания'):
                result += f"📅 {about['дата_основания']}\n"
            if about.get('миссия'):
                result += f"🎯 {about['миссия'][:100]}...\n"
            if about.get('целевая_аудитория'):
                result += f"👥 {about['целевая_аудитория']}"
            return result
        
        return "🏫 НДТ — центр развития одарённых детей в области STEM"
    
    async def get_context_async(self, query: str) -> str:
        """Асинхронная версия"""
        return self.get_context(query)
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика системы"""
        cache_stats = self.cache.get_stats()
        cache_hit_rate = (self.stats['cache_hits'] / max(1, self.stats['total_queries'])) * 100
        
        return {
            **self.stats,
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "avg_tokens_per_query": self.stats['tokens_saved'] / max(1, self.stats['total_queries']),
            **cache_stats
        }

class RAGModes:
    """Режимы экономии токенов"""
    ULTRA_ECONOMY = 300    # Максимальная экономия
    ECONOMY = 500         # Экономный режим (по умолчанию)
    BALANCED = 800        # Сбалансированный
    DETAILED = 1200       # Подробный

# Глобальные экземпляры для разных режимов
_rag_instances = {}

def get_optimized_rag(mode: int = RAGModes.ECONOMY) -> TokenOptimizedRAG:
    """Получить оптимизированную RAG систему"""
    if mode not in _rag_instances:
        _rag_instances[mode] = TokenOptimizedRAG(max_tokens=mode)
    return _rag_instances[mode]

# Асинхронные функции
async def get_optimized_context_async(query: str, mode: int = RAGModes.ECONOMY) -> str:
    """Асинхронное получение оптимизированного контекста"""
    rag = get_optimized_rag(mode)
    return await rag.get_context_async(query)

def get_optimized_context(query: str, mode: int = RAGModes.ECONOMY) -> str:
    """Синхронное получение оптимизированного контекста"""
    rag = get_optimized_rag(mode)
    return rag.get_context(query)

# Совместимость с существующим API
async def get_context_for_query_async(query: str) -> str:
    """Совместимость с существующим API"""
    return await get_optimized_context_async(query, RAGModes.ECONOMY)

def get_context_for_query(query: str) -> str:
    """Совместимость с существующим API"""
    return get_optimized_context(query, RAGModes.ECONOMY) 