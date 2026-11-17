"""Build chapter 12 from its editable source and diagrams."""
from build_chapter01 import ROOT, build
from chapter_figures_07_13 import BUILDERS

if __name__ == '__main__':
    build(source=ROOT/'docs/ja/11-application-deployment.md', chapter=11,
          diagram_builder=BUILDERS[11], report_name='chapter11.validation.public.json',
          new_page_headings=('章末問題', '章末解答', '参考資料'),
          extra_css='h1,h2,h3{overflow-wrap:anywhere}')
