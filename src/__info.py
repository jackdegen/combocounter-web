PLAYER_COLUMNS = {
    'NBA': {
        'classic': ['PG','SG','SF','PF','C','G','F','UTIL'],
        'showdown': ['CPT'] + [f'UTIL{n+1}' for n in range(5)], # May cause issues with multiple columns of same name in pandas
    },

    'NFL': {
        'classic': ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST'],
        'showdown': ['CPT'] + [f'FLEX{n+1}' for n in range(5)], # FLEX in NFL, UTIL in NBA
    },

    'PGA': {
        'classic': [f'G{n+1}' for n in range(5)],
        'showdown': [f'G{n+1}' for n in range(5)],
    }
}
