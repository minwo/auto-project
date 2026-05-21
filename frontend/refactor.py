import sys

def modify():
    with open('app/page.tsx', encoding='utf-8') as f:
        lines = f.readlines()
        
    banner_idx = next(i for i, l in enumerate(lines) if l.startswith('function MarketRegimeBanner'))
    
    # insert imports
    imports = [
        'import { MarketRegimeBanner } from "@/components/MarketRegimeBanner";\n',
        'import { Metric } from "@/components/Metric";\n',
        'import { SignalDetail } from "@/components/SignalDetail";\n'
    ]
    
    new_lines = []
    inserted = False
    for i in range(banner_idx):
        if not inserted and lines[i].startswith('import Link'):
            new_lines.extend(imports)
            inserted = True
        new_lines.append(lines[i])
        
    with open('app/page.tsx', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == '__main__':
    modify()
