import datetime
import math
import re
import sqlglot
from sqlglot import exp

OPS = {exp.EQ: '=', exp.NEQ: '!=', exp.GT: '>', exp.GTE: '>=', exp.LT: '<', exp.LTE: '<='}
DATE_COLUMNS = {'date', 'datetime', 'birth_datetime'}


def _parse(sql):
    try:
        statements = sqlglot.parse(sql, read='postgres')
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f'Invalid SQL: {exc}') from exc
    if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union)):
        raise ValueError('Exactly one SELECT query is required')
    return statements[0]


def _literal(node):
    if isinstance(node, exp.Boolean):
        return bool(node.this), 'boolean'
    if isinstance(node, exp.Literal):
        if node.is_string:
            return node.this, 'string'
        try:
            return int(node.this), 'integer'
        except ValueError:
            try:
                return float(node.this), 'float'
            except ValueError:
                return None
    if isinstance(node, exp.Neg) and isinstance(node.this, exp.Literal) and not node.this.is_string:
        result = _literal(node.this)
        return (-result[0], result[1]) if result else None
    if isinstance(node, exp.Cast) and isinstance(node.this, exp.Literal) and node.this.is_string:
        target = node.args.get('to')
        if target and 'DATE' in target.sql().upper():
            return node.this.this, 'date'
    return None


def _column(node):
    return node if isinstance(node, exp.Column) else None


def _alias_tables(statement):
    aliases = {}
    for table in statement.find_all(exp.Table):
        aliases[table.alias_or_name.lower()] = table.name.lower()
    return aliases


def _semantic(column, statement):
    """Only recognize concepts when table identity can be established."""
    if not column:
        return None
    aliases = _alias_tables(statement)
    name = column.name.lower()
    alias = column.table.lower() if column.table else ''
    table = aliases.get(alias) if alias else None
    if table is None and not alias and len(set(aliases.values())) == 1:
        table = next(iter(aliases.values()))
    direct = {
        'person': {'gender_concept_id', 'race_concept_id', 'ethnicity_concept_id'},
        'visit_occurrence': {'visit_concept_id'},
        'condition_occurrence': {'condition_concept_id'},
        'measurement': {'measurement_concept_id'},
    }
    if name in direct.get(table, set()):
        return name
    # Only interpret concept.name/id when JOIN links it to person.gender_concept_id.
    if table == 'concept' and name in {'concept_name', 'concept_id'}:
        for eq in statement.find_all(exp.EQ):
            left, right = eq.this, eq.expression
            if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
                continue
            pair = ((left, right), (right, left))
            for concept_col, person_col in pair:
                if (concept_col.table.lower() == alias and concept_col.name.lower() == 'concept_id'
                    and person_col.name.lower() == 'gender_concept_id'
                    and aliases.get(person_col.table.lower()) == 'person'):
                    return 'gender_concept_name' if name == 'concept_name' else 'gender_concept_id'
    return None


def _parameter(node, side, literal, pid, ptype, column, operator, statement):
    value, value_type = literal
    if value_type == 'string' and column is not None:
        colname = column.name.lower()
        if colname.endswith('_date') or colname.endswith('_datetime') or colname in DATE_COLUMNS:
            try:
                datetime.date.fromisoformat(value[:10])
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    value_type = 'date'
            except ValueError:
                pass
    return dict(id=pid, type=ptype, column=column.sql(dialect='postgres') if column else None,
                operator=operator, value=value, value_type=value_type, literal_side=side,
                semantic_field=_semantic(column, statement))


def _nodes(statement):
    result = []
    seen = set()
    for where in statement.find_all(exp.Where):
        for node in where.walk():
            if id(node) in seen:
                continue
            seen.add(id(node))
            if isinstance(node, exp.Between):
                col = _column(node.this)
                low, high = _literal(node.args.get('low')), _literal(node.args.get('high'))
                if col is not None and low is not None and high is not None:
                    for side, literal in (('low', low), ('high', high)):
                        result.append((node, _parameter(node, side, literal, len(result),
                                        'between_lower' if side == 'low' else 'between_upper',
                                        col, 'BETWEEN', statement)))
                continue
            symbol = next((s for cls, s in OPS.items() if isinstance(node, cls)), None)
            if symbol is None:
                continue
            left, right = node.this, node.expression
            if _column(left) is not None and _literal(right) is not None:
                result.append((node, _parameter(node, 'right', _literal(right), len(result),
                                                 'comparison', left, symbol, statement)))
            elif _column(right) is not None and _literal(left) is not None:
                result.append((node, _parameter(node, 'left', _literal(left), len(result),
                                                 'comparison', right, symbol, statement)))
    for limit in statement.find_all(exp.Limit):
        lit = _literal(limit.expression)
        if lit and lit[1] == 'integer' and lit[0] >= 0:
            result.append((limit, _parameter(limit, 'expression', lit, len(result),
                                             'limit', None, 'LIMIT', statement)))
    return result


def extract_parameters(sql):
    return [p for _, p in _nodes(_parse(sql))]


def _new_literal(value, kind, old_node=None):
    if kind == 'boolean':
        if not isinstance(value, bool):
            raise ValueError('Expected boolean')
        return exp.Boolean(this=value)
    if kind == 'integer':
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError('Expected integer')
        return exp.Literal.number(value) if value >= 0 else exp.Neg(this=exp.Literal.number(-value))
    if kind == 'float':
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError('Expected finite number')
        return exp.Literal.number(str(value)) if value >= 0 else exp.Neg(this=exp.Literal.number(str(-value)))
    if kind == 'date':
        if isinstance(value, datetime.date):
            value = value.isoformat()
        try:
            datetime.date.fromisoformat(str(value))
        except ValueError as exc:
            raise ValueError('Expected ISO date') from exc
        if isinstance(old_node, exp.Cast):
            copied = old_node.copy()
            copied.set('this', exp.Literal.string(str(value)))
            return copied
        return exp.Literal.string(str(value))
    if kind == 'string':
        if not isinstance(value, str):
            raise ValueError('Expected text')
        return exp.Literal.string(value)
    raise ValueError(f'Unsupported type: {kind}')


def update_parameter(sql, parameter_id, new_value):
    statement = _parse(sql)
    nodes = _nodes(statement)
    if isinstance(parameter_id, bool) or not isinstance(parameter_id, int) or not 0 <= parameter_id < len(nodes):
        raise ValueError('Invalid parameter ID')
    node, parameter = nodes[parameter_id]
    side = parameter['literal_side']
    old = node.args.get({'left': 'this', 'right': 'expression'}.get(side, side))
    literal = _new_literal(new_value, parameter['value_type'], old)
    if parameter['type'] == 'limit':
        if not isinstance(new_value, int) or isinstance(new_value, bool) or new_value < 1:
            raise ValueError('LIMIT must be positive')
        node.set('expression', literal)
    elif parameter['type'] in ('between_lower', 'between_upper'):
        other_side = 'high' if side == 'low' else 'low'
        other = _literal(node.args.get(other_side))
        if other is not None and parameter['value_type'] in ('integer', 'float', 'date'):
            a, b = (new_value, other[0]) if side == 'low' else (other[0], new_value)
            if a > b:
                raise ValueError('The lower bound cannot exceed the upper bound')
        node.set(side, literal)
    elif parameter['type'] == 'comparison':
        node.set('expression' if side == 'right' else 'this', literal)
    else:
        raise ValueError('Unsupported parameter')
    return statement.sql(dialect='postgres')
