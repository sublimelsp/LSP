NON_MODIFIER_SCOPES = {
                'variable': 'variable.other.lsp',
                'parameter': 'variable.parameter.lsp',
                'function': 'variable.function.lsp',
                'method': 'variable.function.lsp',
                'property': 'variable.other.member.lsp',
                'class': 'support.type.lsp',
                'enum': 'variable.enum.lsp',
                'enumMember': 'constant.other.enum.lsp',
                'type': 'storage.type.lsp',
                'macro': 'variable.other.constant.lsp',
                'namespace': 'variable.other.namespace.lsp',
                'typeParameter': 'variable.parameter.generic.lsp',
                'comment': 'comment.block.documentation.lsp',
                'dependent': '',
                'concept': '',
                'module': '',
                'magicFunction': '',
                'selfParameter': '',

            }

DECLARATION_SCOPES = {
            'namespace': 'entity.name.namespace.lsp',
            'type': 'entity.name.type.lsp',
            'class': 'entity.name.class.lsp',
            'enum': 'entity.name.enum.lsp',
            'interface': 'entity.name.interface.lsp',
            'struct': 'entity.name.struct.lsp',
            'function': 'entity.name.function.lsp',
            'method': 'entity.name.function.lsp',
            'macro': 'entity.name.macro.lsp'
            }

STAIC_SCOPES = NON_MODIFIER_SCOPES.copy()
DEPRECATED_SCOPES = NON_MODIFIER_SCOPES.copy()
ABSTRACT_SCOPES = NON_MODIFIER_SCOPES.copy()
ASYNC_SCOPES = NON_MODIFIER_SCOPES.copy()
MODIFICATION_SCOPES = NON_MODIFIER_SCOPES.copy()
DEFAULT_LIB_SCOPES = NON_MODIFIER_SCOPES.copy()

[NON_MODIFIER_SCOPES.update({k: v + ' meta.semantic.' + k + '.lsp'}) for k, v in NON_MODIFIER_SCOPES.items()]

[DECLARATION_SCOPES.update({k: v + ' meta.semantic.' + k + '.declaration.lsp'}) for k, v in DECLARATION_SCOPES.items()]
[STAIC_SCOPES.update({k: v + ' meta.semantic.' + k + '.satic.lsp'}) for k, v in STAIC_SCOPES.items()]
[DEPRECATED_SCOPES.update({k: v + ' meta.semantic.' + k + '.deprecated.lsp'}) for k, v in DEPRECATED_SCOPES.items()]
[ABSTRACT_SCOPES.update({k: v + ' meta.semantic.' + k + '.abstract.lsp'}) for k, v in ABSTRACT_SCOPES.items()]
[ASYNC_SCOPES.update({k: v + ' meta.semantic.' + k + '.async.lsp'}) for k, v in ASYNC_SCOPES.items()]
[MODIFICATION_SCOPES.update({k: v + ' meta.semantic.' + k + '.modification.lsp'})
 for k, v in MODIFICATION_SCOPES.items()]
[DEFAULT_LIB_SCOPES.update({k: v + ' meta.semantic.' + k + '.defaultLibrary.lsp'})
 for k, v in DEFAULT_LIB_SCOPES.items()]

SEMANTIC_SCOPES = {
            '': NON_MODIFIER_SCOPES,  # if no modifiers are provided
            "declaration": DECLARATION_SCOPES,
            "definition": DECLARATION_SCOPES,
            "readonly": {'variable': 'constant.other.lsp, semantic.variable.readonly.lsp'},
            "static": STAIC_SCOPES,  # these are temporary, should be filled with real scopes
            "deprecated": DEPRECATED_SCOPES,
            "abstract": ABSTRACT_SCOPES,
            "async": ASYNC_SCOPES,
            "modification": MODIFICATION_SCOPES,
            "documentation": {'comment': 'comment.block.documentation'},
            "defaultLibrary": DEFAULT_LIB_SCOPES
        }


def get_semantic_scope_from_modifier(encoded_token: list, semantic_tokens_legends: dict) -> str:
    token_int = encoded_token[3]
    modifier_int = encoded_token[4]

    token_type = semantic_tokens_legends['tokenTypes'][token_int]

    if not modifier_int:
        try:
            return(SEMANTIC_SCOPES[''][token_type])
        except KeyError:
            pass  # print('scope not defined for tokenType: ', token_type)

    modifier_binary = [int(x) for x in reversed(bin(modifier_int)[2:])]
    modifiers = [semantic_tokens_legends['tokenModifiers'][i] for i in range(len(modifier_binary)) if i]

    # print('tokenType: ' + token_type + '-- modifiers: ',modifiers)
    scopes = []
    for modifier in modifiers:
        scope = None
        try:
            scope = SEMANTIC_SCOPES[modifier][token_type]
        except KeyError:
            pass  # print('scope not defined for modifier/tokenType: ', modifier+'/'+token_type)

        if scope and scope not in scopes:
            scopes.append(scope)

    if not scopes:
        try:
            return(SEMANTIC_SCOPES[''][token_type])
        except KeyError:
            pass  # print('scope not defined for tokenType: ', token_type)
    else:
        return ', '.join(scopes)

    return ''
