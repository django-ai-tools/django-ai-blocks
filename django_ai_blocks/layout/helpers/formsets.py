from django.forms import modelformset_factory

from django_ai_blocks.layout.models import LayoutBlock
from django_ai_blocks.layout.forms import LayoutBlockForm


def get_layoutblock_formset():
    return modelformset_factory(
        LayoutBlock,
        form=LayoutBlockForm,
        fields=(
            "col_span",
            "row_span",
            "title",
            "note",
            "preferred_filter_name",
            "preferred_column_config_name",
        ),
        extra=0,
    )
