import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
import hashlib

class PDFElementDB:
    def __init__(self, db_path: str = "data/pdf_elements.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pdf_files (
                    file_id TEXT PRIMARY KEY,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    last_processed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS elements (
                    element_id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    element_type TEXT NOT NULL,  -- 'text'/'figure'/'table'/'formula'
                    content TEXT,
                    binary_data BLOB,
                    page_num INTEGER NOT NULL,
                    element_index INTEGER NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES pdf_files (file_id)
                )
            """)
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(self.db_path))

    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def store_pdf_elements(self, file_path: str, elements: List[Dict]) -> str:
        """
        存储PDF元素到数据库
        :param file_path: PDF文件路径
        :param elements: 元素列表，每个元素是包含type/content/page_num等的字典
        :return: 文件ID
        """
        file_hash = self._calculate_file_hash(file_path)
        file_id = hashlib.md5(file_path.encode()).hexdigest()

        with self._get_connection() as conn:
            # 插入或更新PDF文件记录
            conn.execute("""
                INSERT OR REPLACE INTO pdf_files (file_id, file_path, file_hash)
                VALUES (?, ?, ?)
            """, (file_id, str(Path(file_path).absolute()), file_hash))
            
            # 删除旧元素（如果存在）
            conn.execute("DELETE FROM elements WHERE file_id = ?", (file_id,))
            
            # 插入新元素
            for idx, element in enumerate(elements):
                element_id = f"{file_id}_{element['element_type']}_{idx}"
                conn.execute("""
                    INSERT INTO elements (
                        element_id, file_id, element_type, 
                        content, binary_data, page_num, element_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    element_id,
                    file_id,
                    element['element_type'],
                    element.get('content'),
                    element.get('binary_data'),
                    element['page_num'],
                    idx
                ))
            
            conn.commit()
        return file_id

    def get_elements_by_file(self, file_path: str) -> List[Dict]:
        """根据文件路径获取所有元素"""
        file_id = hashlib.md5(file_path.encode()).hexdigest()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT element_type, content, binary_data, page_num, element_index
                FROM elements
                WHERE file_id = ?
                ORDER BY page_num, element_index
            """, (file_id,))
            
            return [{
                'element_type': row[0],
                'content': row[1],
                'binary_data': row[2],
                'page_num': row[3],
                'element_index': row[4]
            } for row in cursor.fetchall()]