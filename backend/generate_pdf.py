from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.colors import HexColor

def generate_pdf():
    doc = SimpleDocTemplate("/Users/diogogomes/Documents/GitHub/ao-rag/backend/data/documents/Guia_Protecao_Civil_Sismos.pdf", pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        textColor=HexColor('#1f2937'),
        alignment=1 # Center
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=15,
        spaceAfter=10,
        textColor=HexColor('#3b82f6')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=10,
        leading=16
    )

    story = []
    
    # Title
    story.append(Paragraph("Manual Oficial de Autoproteção - Sismos", title_style))
    story.append(Paragraph("Diretrizes de Proteção Civil e Prevenção Sísmica em Portugal", body_style))
    story.append(Spacer(1, 20))
    
    # Section 1
    story.append(Paragraph("1. O Que Fazer ANTES de um Sismo (Prevenção)", heading_style))
    story.append(Paragraph("A preparação é a chave para minimizar os danos físicos e materiais:", body_style))
    
    items_before = [
        Paragraph("<b>Fixe os móveis:</b> Aparafuse estantes, vitrines e móveis pesados às paredes.", body_style),
        Paragraph("<b>Organize objetos:</b> Coloque os objetos mais pesados nas prateleiras mais baixas.", body_style),
        Paragraph("<b>Kit de Emergência:</b> Tenha sempre preparado um kit com: água engarrafada, comida enlatada, rádio a pilhas, lanterna, estojo de primeiros socorros e medicação essencial.", body_style),
        Paragraph("<b>Cortes de segurança:</b> Saiba onde estão as válvulas de corte de água, gás e o quadro elétrico e como desligá-los.", body_style)
    ]
    story.append(ListFlowable([ListItem(item) for item in items_before], bulletType='bullet'))
    
    # Section 2
    story.append(Paragraph("2. O Que Fazer DURANTE um Sismo (Ação)", heading_style))
    story.append(Paragraph("A regra de ouro durante um abalo sísmico é: <b>BAIXAR, PROTEGER e AGUARDAR</b>.", body_style))
    
    items_during = [
        Paragraph("<b>Se estiver dentro de casa:</b> Não corra para as escadas! Baixe-se e proteja-se debaixo de uma mesa robusta, ou num canto de uma parede-mestra. Afaste-se de janelas e espelhos.", body_style),
        Paragraph("<b>Elevadores:</b> NUNCA utilize o elevador durante ou imediatamente após um sismo.", body_style),
        Paragraph("<b>Se estiver na rua:</b> Afaste-se de edifícios antigos, postes de eletricidade, muros e árvores. Dirija-se para um local aberto.", body_style),
        Paragraph("<b>Se estiver a conduzir:</b> Pare o veículo num local seguro (longe de pontes ou edifícios) e permaneça no interior do veículo.", body_style)
    ]
    story.append(ListFlowable([ListItem(item) for item in items_during], bulletType='bullet'))
    
    # Section 3
    story.append(Paragraph("3. O Que Fazer DEPOIS de um Sismo (Recuperação)", heading_style))
    
    items_after = [
        Paragraph("Mantenha a calma e prepare-se para as <b>réplicas</b> (tremores secundários que se seguem ao sismo principal).", body_style),
        Paragraph("Corte imediatamente o gás, eletricidade e água se suspeitar de fugas ou danos nas infraestruturas.", body_style),
        Paragraph("Não acenda fósforos nem isqueiros. Utilize apenas lanternas a pilhas.", body_style),
        Paragraph("Ligue o rádio a pilhas e siga as instruções transmitidas pelas autoridades de Proteção Civil.", body_style),
        Paragraph("Use o telemóvel apenas para emergências vitais, para não congestionar as redes de comunicações.", body_style)
    ]
    story.append(ListFlowable([ListItem(item) for item in items_after], bulletType='bullet'))

    # Section 4
    story.append(Paragraph("4. Contexto Sismotectónico de Portugal", heading_style))
    story.append(Paragraph("Portugal continental e os Açores encontram-se em zonas de elevada atividade sísmica devido à fronteira entre as placas Euroasiática e Africana. O Sismo de 1755 (Magnitude ~8.5) e o Sismo de 1969 (Magnitude ~7.9) são exemplos do potencial destrutivo da Falha Açores-Gibraltar.", body_style))

    doc.build(story)

if __name__ == "__main__":
    generate_pdf()
