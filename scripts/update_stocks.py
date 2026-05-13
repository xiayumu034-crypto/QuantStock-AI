import akshare as ak
import json
import os

def update_to_csi300():
    print("正在从 akshare 获取沪深 300 成分股列表...")
    try:
        # 获取沪深300成分股
        df = ak.index_stock_cons(symbol="000300")
        if df.empty:
            print("获取失败：数据为空")
            return
        
        stock_dict = {}
        for _, row in df.iterrows():
            code = str(row['品种代码']).zfill(6)
            name = str(row['品种名称'])
            stock_dict[code] = name
            
        # 写入 data/stock_names.json
        target_path = os.path.join("data", "stock_names.json")
        os.makedirs("data", exist_ok=True)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(stock_dict, f, ensure_ascii=False, indent=4)
            
        print(f"成功更新！当前核心池已扩容至 {len(stock_dict)} 只沪深 300 成分股。")
        
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    update_to_csi300()
