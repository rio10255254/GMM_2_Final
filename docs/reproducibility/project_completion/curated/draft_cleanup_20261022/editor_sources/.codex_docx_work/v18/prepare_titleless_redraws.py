from __future__ import annotations

import shutil
from pathlib import Path


WORK = Path(r"D:\GMM_2_Final\PSF_Fitting\.codex_docx_work")
OUT = WORK / "v18" / "scripts"


COMMON = r'''

function cleanFigure(fig)
% Keep only axes labels, legends, ticks and visual marks.  Explanatory text
% is deliberately moved to the Word caption.
axesList = findall(fig, 'Type', 'axes');
for k = 1:numel(axesList)
    ax = axesList(k);
    if ~isa(ax, 'matlab.graphics.axis.Axes')
        continue;
    end
    ax.Title.String = '';
    ax.Title.Visible = 'off';
    if isprop(ax, 'Subtitle')
        ax.Subtitle.String = '';
        ax.Subtitle.Visible = 'off';
    end
    keep = [ax.XLabel, ax.YLabel, ax.ZLabel];
    notes = findall(ax, 'Type', 'text');
    for n = 1:numel(notes)
        if ~any(notes(n) == keep)
            delete(notes(n));
        end
    end
    refs = findall(ax, 'Type', 'ConstantLine');
    for n = 1:numel(refs)
        if isprop(refs(n), 'Label')
            refs(n).Label = '';
        end
    end
end
end
'''


def write_clean(source_name: str, dest_name: str, kind: str) -> None:
    content = (WORK / source_name).read_text(encoding="utf-8")
    content = content.replace("v17_chinese_figures", r"v18\figures")
    if kind == "early":
        content = content.replace("exportgraphics(fig,", "cleanFigure(fig); exportgraphics(fig,")
        content = content.replace("sprintf('重建損失（下降 %.1f%%）',reductions(1))", "'重建損失'")
        content = content.replace("sprintf('梯度幅值損失（下降 %.1f%%）',reductions(2))", "'梯度幅值損失'")
        content = content.replace("sprintf('邊緣方向損失（下降 %.1f%%）',reductions(3))", "'邊緣方向損失'")
        content = content.replace(
            "rectangle(ax,'Position',pillarRect,'EdgeColor',pillarColor,'LineWidth',1.6,'LineStyle','--'); rectangle(ax,'Position',viaRect,'EdgeColor',viaColor,'LineWidth',1.6,'LineStyle','--');\n"
            "rectangle(ax,'Position',[cropRect(1),cropRect(2),cropRect(3)-cropRect(1),cropRect(4)-cropRect(2)],'EdgeColor',[0 0 0],'LineWidth',4.5); rectangle(ax,'Position',[cropRect(1),cropRect(2),cropRect(3)-cropRect(1),cropRect(4)-cropRect(2)],'EdgeColor',selectionColor,'LineWidth',2.6);\n"
            "plot(ax,centers(:,1),centers(:,2),'o','MarkerSize',4.2,'MarkerEdgeColor',[0 0 0],'MarkerFaceColor',selectionColor);\n"
            "plot(ax,sampleCenter(1),sampleCenter(2),'p','MarkerSize',10,'MarkerEdgeColor',[0 0 0],'MarkerFaceColor',[1 1 1]);",
            "hPillar=rectangle(ax,'Position',pillarRect,'EdgeColor',pillarColor,'LineWidth',1.6,'LineStyle','--','DisplayName','pillar區域'); hVia=rectangle(ax,'Position',viaRect,'EdgeColor',viaColor,'LineWidth',1.6,'LineStyle','--','DisplayName','via區域');\n"
            "rectangle(ax,'Position',[cropRect(1),cropRect(2),cropRect(3)-cropRect(1),cropRect(4)-cropRect(2)],'EdgeColor',[0 0 0],'LineWidth',4.5,'HandleVisibility','off'); hSelection=rectangle(ax,'Position',[cropRect(1),cropRect(2),cropRect(3)-cropRect(1),cropRect(4)-cropRect(2)],'EdgeColor',selectionColor,'LineWidth',2.6,'DisplayName','中心3×3 pillar');\n"
            "plot(ax,centers(:,1),centers(:,2),'o','MarkerSize',4.2,'MarkerEdgeColor',[0 0 0],'MarkerFaceColor',selectionColor,'HandleVisibility','off');\n"
            "hCenter=plot(ax,sampleCenter(1),sampleCenter(2),'p','MarkerSize',10,'MarkerEdgeColor',[0 0 0],'MarkerFaceColor',[1 1 1],'DisplayName','樣品中心交界');",
        )
        content = content.replace(
            "text(ax,(x1+x2)/2,y-8,sprintf('%g \\mum',scaleBarUm),'Color','w','FontSize',9,'HorizontalAlignment','center','VerticalAlignment','bottom','FontWeight','bold','Interpreter','tex');\nexportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);",
            "text(ax,(x1+x2)/2,y-8,sprintf('%g \\mum',scaleBarUm),'Color','w','FontSize',9,'HorizontalAlignment','center','VerticalAlignment','bottom','FontWeight','bold','Interpreter','tex');\nlegend(ax,[hPillar,hVia,hSelection,hCenter],'Location','southoutside','NumColumns',2,'Box','off');\ncleanFigure(fig); exportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);",
        )
    elif kind == "wiener":
        content = content.replace(
            "function exportFigure(fig,path), set(fig,'Renderer','painters');axesList=findall(fig,'Type','axes');for k=1:numel(axesList),axtoolbar(axesList(k),{});end;exportgraphics(fig,path,'Resolution',300,'BackgroundColor','white');close(fig);end",
            "function exportFigure(fig,path), cleanFigure(fig); set(fig,'Renderer','painters');axesList=findall(fig,'Type','axes');for k=1:numel(axesList),axtoolbar(axesList(k),{});end;exportgraphics(fig,path,'Resolution',300,'BackgroundColor','white');close(fig);end",
        )
    elif kind == "r63":
        content = content.replace(
            "function export_pair(fig, folder, stem)\nexportgraphics(fig, fullfile(folder, [stem '.png']), 'Resolution', 300);",
            "function export_pair(fig, folder, stem)\ncleanFigure(fig);\nexportgraphics(fig, fullfile(folder, [stem '.png']), 'Resolution', 300);",
        )
    elif kind in {"via", "fig36"}:
        content = content.replace("exportgraphics(fig,", "cleanFigure(fig); exportgraphics(fig,")
    else:
        raise ValueError(kind)
    content += COMMON
    dest = OUT / dest_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    write_clean("generate_v17_ch6_early_figures_zh.m", "generate_v18_ch6_early_figures_clean.m", "early")
    write_clean("build_wiener_three_way_chapter62_figures_zh.m", "build_wiener_three_way_chapter62_figures_clean.m", "wiener")
    write_clean("build_r63_figures_zh.m", "build_r63_figures_clean.m", "r63")
    write_clean("generate_v17_via_line_zh.m", "generate_v18_via_line_clean.m", "via")
    write_clean("generate_v17_fig36_zh.m", "generate_v18_fig36_clean.m", "fig36")
    print(OUT)


if __name__ == "__main__":
    main()
