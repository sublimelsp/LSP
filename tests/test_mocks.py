from __future__ import annotations

from LSP.plugin.core.types import ClientConfig

TEST_CONFIG = ClientConfig(name="test", command=[], selector="text.plain", tcp_port=None)
DISABLED_CONFIG = ClientConfig(name="test", command=[], selector="text.plain", tcp_port=None, enabled=False)

basic_responses = {
    'initialize': {
        'capabilities': {
            'testing': True,
            'hoverProvider': True,
            'completionProvider': {
                'triggerCharacters': ['.'],
                'resolveProvider': True
            },
            'textDocumentSync': {
                "openClose": True,
                "change": 2,
                "save": True
            },
            'definitionProvider': True,
            'typeDefinitionProvider': True,
            'declarationProvider': True,
            'implementationProvider': True,
            'documentFormattingProvider': True,
            'selectionRangeProvider': True,
            'renameProvider': True,
            'workspace': {
                'workspaceFolders': {
                    'supported': True
                }
            }
        }
    }
}
