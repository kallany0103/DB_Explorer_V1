# dialogs/properties/__init__.py

from .table_properties import TablePropertiesDialog
from .schema_properties import SchemaPropertiesDialog
from .function_properties import FunctionPropertiesDialog
from .sequence_properties import SequencePropertiesDialog
from .extension_properties import ExtensionPropertiesDialog
from .language_properties import LanguagePropertiesDialog
from .foreign_data_properties import FDWPropertiesDialog, ForeignServerPropertiesDialog, UserMappingPropertiesDialog

__all__ = [
    'TablePropertiesDialog', 
    'SchemaPropertiesDialog', 
    'FunctionPropertiesDialog', 
    'SequencePropertiesDialog',
    'ExtensionPropertiesDialog',
    'LanguagePropertiesDialog',
    'FDWPropertiesDialog',
    'ForeignServerPropertiesDialog',
    'UserMappingPropertiesDialog'
]
