import os
import json
import uuid
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModernRAGSystem:
    """Современная RAG система с векторным поиском на основе эмбеддингов"""
    
    def __init__(
        self, 
        knowledge_base_path: str = "knowledge_base.json",
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        db_path: str = "./chroma_db"
    ):
        self.knowledge_base_path = Path(knowledge_base_path)
        self.db_path = db_path
        self.collection_name = "technopark_knowledge"
        self.last_indexed = None
        
        # Инициализация модели эмбеддингов
        logger.info(f"🤖 Загрузка модели эмбеддингов: {model_name}")
        self.embedding_model = SentenceTransformer(model_name)
        
        # Инициализация ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        
        # Создаем или получаем коллекцию
        try:
            self.collection = self.chroma_client.get_collection(self.collection_name)
        except Exception:
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "База знаний технопарка"}
            )
        
        self.knowledge_base = {}
        logger.info("✅ Современная RAG система инициализирована")
    
    def load_and_index_knowledge(self):
        """Загрузка и индексирование базы знаний"""
        try:
            # Проверяем, нужно ли переиндексировать
            if self._need_reindexing():
                logger.info("🔄 Начинаем переиндексирование базы знаний...")
                self._load_knowledge_base()
                self._create_embeddings()
                self.last_indexed = datetime.now()
                logger.info("✅ Индексирование завершено")
            else:
                logger.info("📚 База знаний уже актуальна")
                self._load_knowledge_base()
                
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке базы знаний: {e}")
            self.knowledge_base = {}
    
    def _need_reindexing(self) -> bool:
        """Проверка, нужно ли переиндексировать базу знаний"""
        if not self.knowledge_base_path.exists():
            return False
        
        # Проверяем количество документов в коллекции
        count = self.collection.count()
        if count == 0:
            return True
        
        # Проверяем время последнего изменения файла
        file_mtime = datetime.fromtimestamp(self.knowledge_base_path.stat().st_mtime)
        if self.last_indexed is None or file_mtime > self.last_indexed:
            return True
        
        return False
    
    def _load_knowledge_base(self):
        """Загрузка базы знаний из JSON"""
        try:
            with open(self.knowledge_base_path, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)
            logger.info(f"📖 База знаний загружена: {list(self.knowledge_base.keys())}")
        except FileNotFoundError:
            logger.error(f"❌ Файл {self.knowledge_base_path} не найден")
            self.knowledge_base = {}
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка JSON: {e}")
            self.knowledge_base = {}
    
    def _create_embeddings(self):
        """Создание эмбеддингов для всех документов под новую структуру JSON"""
        if not self.knowledge_base:
            logger.warning("⚠️ База знаний пуста")
            return

        # Очищаем коллекцию перед переиндексированием
        try:
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "База знаний технопарка"}
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось очистить коллекцию: {e}")

        documents = []
        metadatas = []
        ids = []

        # 1. Обработка общей информации о технопарке
        about_info = self.knowledge_base.get("о_технопарке", {})
        if about_info:
            doc_text = self._format_document(about_info, "about")
            documents.append(doc_text)
            metadatas.append({
                "section": "about",
                "type": "general_info",
                "title": "Общая информация о технопарке"
            })
            ids.append(str(uuid.uuid4()))

        # 2. Обработка образовательных направлений
        directions = self.knowledge_base.get("образовательные_направления", [])
        for i, direction in enumerate(directions):
            doc_text = self._format_document(direction, "direction")
            documents.append(doc_text)
            metadatas.append({
                "section": "educational_directions",
                "type": "direction",
                "title": direction.get("название", f"Направление {i+1}"),
                "direction_id": str(i)
            })
            ids.append(str(uuid.uuid4()))

        # 2.1. Обработка списка направлений (общий обзор)
        directions_list = self.knowledge_base.get("список_направлений", [])
        if directions_list:
            doc_text = self._format_document({"список": directions_list}, "directions_list")
            documents.append(doc_text)
            metadatas.append({
                "section": "directions_list",
                "type": "directions_overview",
                "title": "Список всех образовательных направлений"
            })
            ids.append(str(uuid.uuid4()))

        # 3. Обработка процедуры отбора
        selection_process = self.knowledge_base.get("процедура_отбора", {})
        if selection_process:
            doc_text = self._format_document(selection_process, "selection")
            documents.append(doc_text)
            metadatas.append({
                "section": "selection",
                "type": "selection_info",
                "title": "Процедура отбора"
            })
            ids.append(str(uuid.uuid4()))

        # 4. Обработка информации для поступления
        admission_info = self.knowledge_base.get("информация_для_поступления", "")
        if admission_info:
            doc_text = self._format_document({"description": admission_info}, "admission")
            documents.append(doc_text)
            metadatas.append({
                "section": "admission",
                "type": "admission_info",
                "title": "Информация для поступления"
            })
            ids.append(str(uuid.uuid4()))

        # 5. Обработка чек-листа документов
        documents_checklist = self.knowledge_base.get("documents_checklist", [])
        if documents_checklist:
            doc_text = self._format_document({"documents": documents_checklist}, "documents")
            documents.append(doc_text)
            metadatas.append({
                "section": "documents",
                "type": "documents_info",
                "title": "Необходимые документы"
            })
            ids.append(str(uuid.uuid4()))

        # 6. Обработка образовательных смен
        sessions_info = self.knowledge_base.get("образовательные_смены", {})
        if sessions_info:
            doc_text = self._format_document(sessions_info, "sessions")
            documents.append(doc_text)
            metadatas.append({
                "section": "sessions",
                "type": "sessions_info",
                "title": "Образовательные смены"
            })
            ids.append(str(uuid.uuid4()))

        # 7. Обработка дистанционного обучения
        remote_learning = self.knowledge_base.get("дистанционное_обучение", {})
        if remote_learning:
            doc_text = self._format_document(remote_learning, "remote")
            documents.append(doc_text)
            metadatas.append({
                "section": "remote_learning",
                "type": "remote_info",
                "title": "Дистанционное обучение"
            })
            ids.append(str(uuid.uuid4()))

        # 8. Обработка информации о проживании
        accommodation = self.knowledge_base.get("проживание", {})
        if accommodation:
            doc_text = self._format_document(accommodation, "accommodation")
            documents.append(doc_text)
            metadatas.append({
                "section": "accommodation",
                "type": "accommodation_info",
                "title": "Проживание в Технодоме"
            })
            ids.append(str(uuid.uuid4()))

        # 9. Обработка требований к проекту
        project_requirements = self.knowledge_base.get("требования_к_проекту", {})
        if project_requirements:
            doc_text = self._format_document(project_requirements, "project_requirements")
            documents.append(doc_text)
            metadatas.append({
                "section": "project_requirements",
                "type": "project_info",
                "title": "Требования к проекту"
            })
            ids.append(str(uuid.uuid4()))

        # 10. Обработка FAQ
        faq_items = self.knowledge_base.get("часто_задаваемые_вопросы", [])
        for i, faq in enumerate(faq_items):
            doc_text = self._format_document(faq, "faq")
            documents.append(doc_text)
            metadatas.append({
                "section": "faq",
                "type": "faq_item",
                "title": faq.get("вопрос", f"FAQ {i+1}"),
                "faq_id": str(i)
            })
            ids.append(str(uuid.uuid4()))

        # 11. Обработка льгот для выпускников
        benefits = self.knowledge_base.get("льготы_для_выпускников", {})
        if benefits:
            doc_text = self._format_document(benefits, "benefits")
            documents.append(doc_text)
            metadatas.append({
                "section": "benefits",
                "type": "benefits_info",
                "title": "Льготы для выпускников"
            })
            ids.append(str(uuid.uuid4()))

        if documents:
            logger.info(f"🔄 Создание эмбеддингов для {len(documents)} документов...")

            # Создаем эмбеддинги
            embeddings = self.embedding_model.encode(documents)

            # Добавляем в ChromaDB
            self.collection.add(
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f"✅ Добавлено {len(documents)} документов в базу")
        else:
            logger.warning("⚠️ Нет документов для индексирования")
    
    def _format_document(self, data: Dict[str, Any], doc_type: str) -> str:
        """Форматирование документа для индексирования под новую структуру JSON"""
        if doc_type == "about":
            parts = []
            if "полное_название" in data:
                parts.append(f"Название: {str(data['полное_название'])}")
            if "описание" in data:
                parts.append(f"Описание: {str(data['описание'])}")
            if "миссия" in data:
                parts.append(f"Миссия: {str(data['миссия'])}")
            if "адрес" in data:
                parts.append(f"Адрес: {str(data['адрес'])}")
            if "дата_основания" in data:
                parts.append(f"Дата основания: {str(data['дата_основания'])}")
            if "целевая_аудитория" in data:
                parts.append(f"Целевая аудитория: {str(data['целевая_аудитория'])}")
            
            # Обрабатываем принципы
            principles = data.get("принципы", [])
            if principles and isinstance(principles, list):
                principles_str = ', '.join([str(p) for p in principles])
                parts.append(f"Принципы: {principles_str}")
            
            # Обрабатываем инфраструктуру
            infrastructure = data.get("инфраструктура", [])
            if infrastructure and isinstance(infrastructure, list):
                infra_str = ', '.join([str(i) for i in infrastructure])
                parts.append(f"Инфраструктура: {infra_str}")
            
            return " | ".join(parts)
        
        elif doc_type == "direction":
            parts = []
            if "название" in data:
                parts.append(f"Направление: {str(data['название'])}")
            if "описание" in data:
                parts.append(f"Описание: {str(data['описание'])}")
            
            return " | ".join(parts)
        
        elif doc_type == "directions_list":
            parts = []
            directions_list = data.get("список", [])
            if directions_list and isinstance(directions_list, list):
                directions_str = ', '.join([str(direction) for direction in directions_list])
                parts.append(f"Все образовательные направления в технопарке: {directions_str}")
                parts.append(f"Всего направлений: {len(directions_list)}")
            
            return " | ".join(parts)
        
        elif doc_type == "selection":
            parts = []
            if "общее_описание" in data:
                parts.append(f"Описание: {str(data['общее_описание'])}")
            
            # Обрабатываем этапы
            stage1 = data.get("этап_1", {})
            if stage1:
                parts.append(f"Этап 1: {stage1.get('название', '')} - {stage1.get('требования', '')}")
            
            stage2 = data.get("этап_2", {})
            if stage2:
                parts.append(f"Этап 2: {stage2.get('название', '')} - {stage2.get('описание', '')}")
            
            return " | ".join(parts)
        
        elif doc_type == "admission":
            parts = []
            if "description" in data:
                parts.append(f"Информация о поступлении: {str(data['description'])}")
            
            return " | ".join(parts)
        
        elif doc_type == "documents":
            parts = []
            documents_list = data.get("documents", [])
            if documents_list and isinstance(documents_list, list):
                docs_str = ', '.join([str(doc.get('name', '')) for doc in documents_list])
                parts.append(f"Необходимые документы: {docs_str}")
            
            return " | ".join(parts)
        
        elif doc_type == "sessions":
            parts = []
            if "описание" in data:
                parts.append(f"Образовательные смены: {str(data['описание'])}")
            
            structure = data.get("структура_смены", [])
            if structure and isinstance(structure, list):
                struct_str = ', '.join([str(s) for s in structure])
                parts.append(f"Структура смены: {struct_str}")
            
            return " | ".join(parts)
        
        elif doc_type == "remote":
            parts = []
            if "описание" in data:
                parts.append(f"Дистанционное обучение: {str(data['описание'])}")
            
            features = data.get("особенности", [])
            if features and isinstance(features, list):
                features_str = ', '.join([str(f) for f in features])
                parts.append(f"Особенности: {features_str}")
            
            return " | ".join(parts)
        
        elif doc_type == "accommodation":
            parts = []
            if "описание" in data:
                parts.append(f"Проживание: {str(data['описание'])}")
            
            infrastructure = data.get("инфраструктура", [])
            if infrastructure and isinstance(infrastructure, list):
                infra_str = ', '.join([str(i) for i in infrastructure])
                parts.append(f"Инфраструктура: {infra_str}")
            
            return " | ".join(parts)
        
        elif doc_type == "project_requirements":
            parts = []
            if "описание" in data:
                parts.append(f"Требования к проекту: {str(data['описание'])}")
            
            structure = data.get("структура", [])
            if structure and isinstance(structure, list):
                struct_str = ', '.join([str(s) for s in structure])
                parts.append(f"Структура проекта: {struct_str}")
            
            return " | ".join(parts)
        
        elif doc_type == "faq":
            parts = []
            if "вопрос" in data:
                parts.append(f"Вопрос: {str(data['вопрос'])}")
            if "ответ" in data:
                parts.append(f"Ответ: {str(data['ответ'])}")
            
            return " | ".join(parts)
        
        elif doc_type == "benefits":
            parts = []
            if "описание" in data:
                parts.append(f"Льготы для выпускников: {str(data['описание'])}")
            
            return " | ".join(parts)
        
        # Общий случай - преобразуем в строку
        return str(data)
    
    async def search_async(
        self, 
        query: str, 
        max_results: int = 3,
        min_score: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Асинхронный поиск релевантной информации"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.search, query, max_results, min_score
        )
    
    def search(
        self, 
        query: str, 
        max_results: int = 3,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Поиск релевантной информации с использованием векторного поиска"""
        logger.info(f"🔍 Векторный поиск по запросу: '{query}'")
        
        if self.collection.count() == 0:
            logger.warning("⚠️ База данных пуста")
            return []
        
        try:
            # Создаем эмбеддинг для запроса
            query_embedding = self.embedding_model.encode([query])
            
            # Выполняем поиск в ChromaDB
            results = self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=max_results * 2,  # Берем больше для фильтрации
                include=['documents', 'metadatas', 'distances']
            )
            
            if not results['documents'] or not results['documents'][0]:
                logger.info("🤷 Релевантные документы не найдены")
                return []
            
            # Обрабатываем результаты
            processed_results = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0], 
                results['distances'][0]
            )):
                # ChromaDB использует squared euclidean distance, конвертируем в similarity
                # Чем меньше distance, тем больше similarity
                similarity = 1 / (1 + distance)  # Нормализация: distance 0 = similarity 1, большой distance = similarity близка к 0
                
                logger.info(f"🔍 Документ: '{metadata.get('title')}' distance: {distance:.3f}, similarity: {similarity:.3f}")
                
                # Фильтруем по минимальному score
                if similarity >= min_score:
                    processed_results.append({
                        "document": doc,
                        "metadata": metadata,
                        "similarity": similarity,
                        "section": metadata.get("section", "unknown"),
                        "title": metadata.get("title", "Без названия"),
                        "type": metadata.get("type", "unknown")
                    })
                    
                    logger.info(f"✅ Найден документ: '{metadata.get('title')}' (similarity: {similarity:.3f})")
            
            # Сортируем по убыванию similarity
            processed_results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Возвращаем топ результатов
            final_results = processed_results[:max_results]
            logger.info(f"📊 Возвращаем {len(final_results)} результатов из {len(processed_results)} найденных")
            
            return final_results
            
        except Exception as e:
            logger.error(f"❌ Ошибка векторного поиска: {e}", exc_info=True)
            return []
    
    def get_context_for_query(self, query: str, max_context_length: int = None) -> str:
        """Умное получение релевантного контекста с динамическим анализом"""
        logger.info(f"🔎 Получение контекста для: '{query}'")
        
        query_lower = query.lower()
        
        # Проверяем на приветствия - не используем RAG
        greeting_words = ['привет', 'здравствуй', 'добро пожаловать', 'начать', 'старт', 'hello', 'hi']
        if len(query_lower.split()) <= 2 and any(word in query_lower for word in greeting_words):
            logger.info("👋 Обнаружено приветствие - не используем RAG контекст")
            return ""
        
        # Умное расширение запроса
        query_expanded = self._expand_query(query_lower)
        logger.info(f"🔧 Расширенный запрос: '{query_expanded}'")
        
        # ЩЕДРЫЙ ПОДХОД: дадим ИИ максимум информации для анализа
        logger.info("🎯 Используем щедрый подход - максимум контекста для ИИ")
        
        # Выполняем поиск с очень низкими порогами
        search_results = self.search(query_expanded, max_results=25, min_score=0.001)
        
        # Если ничего не найдено с расширенным запросом, попробуем оригинальный
        if not search_results:
            logger.info("🔄 Пробуем оригинальный запрос без расширения")
            search_results = self.search(query_lower, max_results=25, min_score=0.001)
        
        # Если все еще ничего - берем просто топ документов
        if not search_results:
            logger.info("🎲 Берем топ документов без учета релевантности")
            search_results = self.search("технопарк", max_results=20, min_score=0.0)
        
        if not search_results:
            logger.warning("❌ Абсолютно никаких результатов не найдено")
            return ""
        
        # УБИРАЕМ ВСЕ ПОРОГИ - берем ВСЕ что нашли
        context_parts = []
        total_length = 0
        used_results = 0
        
        for result in search_results:
            document = result["document"]
            title = result["title"]
            similarity = result["similarity"]
            
            # Берем ВСЕ результаты без фильтрации
            context_parts.append(document)
            total_length += len(document)
            used_results += 1
            logger.info(f"✅ Добавлен: '{title}' (similarity: {similarity:.3f}, {len(document)} символов)")
        
        context = "\n\n".join(context_parts)
        logger.info(f"📝 ЩЕДРЫЙ КОНТЕКСТ: {len(context)} символов из {used_results} результатов")
        
        return context
    
    def _detect_query_intent(self, query: str) -> str:
        """Умное определение типа запроса"""
        # Паттерны для определения интента
        intent_patterns = {
            'directions': ['направления', 'программы', 'курсы', 'специальности', 'изучают', 'обучение', 'кит', 'робо', 'био'],
            'location': ['где', 'адрес', 'находится', 'местоположение', 'расположен', 'добраться', 'тп'],
            'admission': ['поступление', 'поступить', 'отбор', 'документы', 'требования', 'как попасть'],
            'accommodation': ['проживание', 'общежитие', 'технодом', 'жить', 'ночевать'],
            'schedule': ['расписание', 'время', 'когда', 'график', 'смены'],
            'contacts': ['контакты', 'телефон', 'связаться', 'оператор', 'помощь'],
            'general': []  # По умолчанию
        }
        
        for intent, keywords in intent_patterns.items():
            if any(keyword in query for keyword in keywords):
                return intent
        
        return 'general'
    
    def _get_search_parameters(self, intent: str) -> Dict[str, float]:
        """Получение параметров поиска в зависимости от типа запроса"""
        params = {
            'directions': {
                'max_results': 20,
                'min_score': 0.01,
                'relevance_threshold': 0.015,
                'min_filter': 0.01
            },
            'location': {
                'max_results': 10,
                'min_score': 0.01,
                'relevance_threshold': 0.02,
                'min_filter': 0.015
            },
            'admission': {
                'max_results': 15,
                'min_score': 0.02,
                'relevance_threshold': 0.025,
                'min_filter': 0.02
            },
            'accommodation': {
                'max_results': 12,
                'min_score': 0.02,
                'relevance_threshold': 0.025,
                'min_filter': 0.02
            },
            'general': {
                'max_results': 15,
                'min_score': 0.02,
                'relevance_threshold': 0.03,
                'min_filter': 0.02
            }
        }
        
        return params.get(intent, params['general'])
    
    def _expand_query(self, query: str) -> str:
        """Умное расширение запроса с семантическим анализом"""
        expanded_parts = [query]
        
        # 1. Обработка сокращений (только самые очевидные)
        common_abbreviations = {
            'кит': 'информационные компьютерные технологии',
            'ит': 'информационные технологии',
            'вр': 'виртуальная реальность',
            'ар': 'дополненная реальность',
            'тп': 'технопарк'
        }
        
        query_lower = query.lower()
        for abbr, full in common_abbreviations.items():
            if abbr in query_lower:
                expanded_parts.append(full)
        
        # 2. Семантическое расширение на основе контекста базы знаний
        semantic_expansions = self._get_semantic_expansions(query_lower)
        expanded_parts.extend(semantic_expansions)
        
        # 3. Контекстные синонимы на основе анализа запроса
        contextual_terms = self._get_contextual_terms(query_lower)
        expanded_parts.extend(contextual_terms)
        
        # Убираем дубликаты и объединяем
        unique_parts = list(dict.fromkeys(expanded_parts))
        return " ".join(unique_parts)
    
    def _get_semantic_expansions(self, query: str) -> List[str]:
        """Получение семантических расширений на основе анализа базы знаний"""
        expansions = []
        
        # Динамически извлекаем ключевые термины из базы знаний
        kb_terms = self._extract_key_terms()
        
        # Анализируем запрос и находим связанные термины
        query_words = set(query.lower().split())
        
        for category, terms in kb_terms.items():
            # Если хотя бы одно слово из запроса совпадает с категорией
            if any(word in terms for word in query_words):
                # Добавляем все термины этой категории
                expansions.extend(terms)
                
        return list(set(expansions))  # Убираем дубликаты
    
    def _extract_key_terms(self) -> Dict[str, List[str]]:
        """Динамическое извлечение ключевых терминов из базы знаний"""
        terms = {
            'location': [],
            'education': [],
            'admission': [],
            'accommodation': [],
            'general': []
        }
        
        # Извлекаем термины из разных разделов базы знаний
        if 'о_технопарке' in self.knowledge_base:
            about = self.knowledge_base['о_технопарке']
            if 'адрес' in about:
                # Разбиваем адрес на компоненты
                address = about['адрес'].lower()
                terms['location'].extend([
                    'франциска скорины', 'адрес', 'местоположение', 'технопарк'
                ])
                # Добавляем части адреса
                address_parts = address.replace(',', ' ').split()
                terms['location'].extend(address_parts)
        
        # Извлекаем образовательные направления
        if 'образовательные_направления' in self.knowledge_base:
            for direction in self.knowledge_base['образовательные_направления']:
                if 'название' in direction:
                    name = direction['название'].lower()
                    terms['education'].extend(name.split())
        
        # Извлекаем термины из списка направлений
        if 'список_направлений' in self.knowledge_base:
            for direction in self.knowledge_base['список_направлений']:
                terms['education'].extend(direction.lower().split())
        
        # Извлекаем термины из процедуры отбора
        if 'процедура_отбора' in self.knowledge_base:
            terms['admission'].extend(['поступление', 'отбор', 'документы', 'требования'])
        
        # Извлекаем термины из проживания
        if 'проживание' in self.knowledge_base:
            terms['accommodation'].extend(['проживание', 'технодом', 'общежитие'])
        
        # Очищаем и фильтруем термины
        for category in terms:
            # Убираем короткие слова и предлоги
            terms[category] = [
                term.strip().lower() 
                for term in terms[category] 
                if len(term.strip()) > 2 and term.strip() not in ['для', 'как', 'что', 'где', 'это', 'все', 'или', 'при']
            ]
            # Убираем дубликаты
            terms[category] = list(set(terms[category]))
        
        return terms
    
    def _get_contextual_terms(self, query: str) -> List[str]:
        """Получение контекстуальных терминов на основе семантического анализа"""
        contextual_terms = []
        
        # Паттерны для разных типов запросов
        query_patterns = {
            # Локационные запросы
            'location': {
                'keywords': ['где', 'адрес', 'находится', 'местоположение', 'расположен', 'добраться'],
                'context': ['технопарк', 'адрес', 'местоположение', 'контакты']
            },
            # Образовательные запросы
            'education': {
                'keywords': ['направления', 'программы', 'курсы', 'специальности', 'изучают', 'обучение'],
                'context': ['образовательные', 'направления', 'программы', 'обучение']
            },
            # Процедурные запросы
            'admission': {
                'keywords': ['поступление', 'поступить', 'отбор', 'документы', 'требования'],
                'context': ['поступление', 'отбор', 'документы', 'требования']
            },
            # Проживание
            'accommodation': {
                'keywords': ['проживание', 'общежитие', 'технодом', 'жить'],
                'context': ['проживание', 'технодом', 'жилье']
            },
            # Практические вопросы
            'practical': {
                'keywords': ['как', 'что', 'можно', 'нужно', 'необходимо'],
                'context': ['информация', 'помощь', 'консультация']
            }
        }
        
        # Определяем тип запроса и добавляем соответствующий контекст
        for pattern_type, pattern_data in query_patterns.items():
            if any(keyword in query for keyword in pattern_data['keywords']):
                contextual_terms.extend(pattern_data['context'])
                break  # Берем только первый подходящий паттерн
                
        return contextual_terms
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики базы знаний"""
        return {
            "total_documents": self.collection.count(),
            "model_name": self.embedding_model.get_sentence_embedding_dimension(),
            "last_indexed": self.last_indexed.isoformat() if self.last_indexed else None,
            "knowledge_base_sections": list(self.knowledge_base.keys()),
            "collection_name": self.collection_name,
            "db_path": self.db_path
        }
    
    def reload_knowledge_base(self):
        """Принудительная перезагрузка базы знаний"""
        logger.info("🔄 Принудительная перезагрузка базы знаний...")
        self.last_indexed = None
        self.load_and_index_knowledge()


# Глобальная инстанция для использования в других модулях
modern_rag_instance = None

def set_global_instance(instance):
    """Установка глобальной инстанции"""
    global modern_rag_instance
    modern_rag_instance = instance

async def get_context_for_query_async(query: str) -> str:
    """Асинхронная обертка для получения контекста"""
    global modern_rag_instance
    if modern_rag_instance is None:
        return ""
    return modern_rag_instance.get_context_for_query(query)

def get_context_for_query(query: str) -> str:
    """Синхронная обертка для получения контекста"""
    global modern_rag_instance
    if modern_rag_instance is None:
        return ""
    return modern_rag_instance.get_context_for_query(query) 