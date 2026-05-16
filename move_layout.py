import sys

def main():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    start_v0 = content.find('        <!-- V0 广度雷达 -->')
    end_ml = content.find('<div class="modal fade" id="rankAnalysisModal" tabindex="-1">')
    
    if start_v0 == -1 or end_ml == -1:
        print("Couldn't find sections")
        return
        
    block_to_move = content[start_v0:end_ml]
    
    content_without_block = content[:start_v0] + content[end_ml:]
    
    target_idx = content_without_block.find('        <!-- 第四行：主图表 -->')
    
    if target_idx == -1:
        print("Couldn't find target")
        return
        
    final_content = content_without_block[:target_idx] + block_to_move + '\n' + content_without_block[target_idx:]
    
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(final_content)
        
    print("Successfully moved!")

if __name__ == '__main__':
    main()
