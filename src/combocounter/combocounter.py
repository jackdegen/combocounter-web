import itertools

class ComboCounterDict:
    def __init__(self, *, k: int):
        self.__k = k
        self.__data = {k: dict() for k in range(1,k+1)}

    @staticmethod
    def level(key):
        return 1 if isinstance(key, str) or len(key) == 1 else len(key)

    @staticmethod
    def parse_key(key):

        # If single person key, just return it
        if isinstance(key, str):
            return key

        # Otherwise its a tuple
        # Quick linting in case tuple with len == 1
        return key[0] if len(key) == 1 else tuple(sorted(key))

    def __setitem__(self, key, value: int) -> None:
        self.__data[self.level(key)][self.parse_key(key)] = value
        return

    def __getitem__(self, key) -> int:
        return self.__data[self.level(key)][self.parse_key(key)]

    def get(self, key, default=0):
        return self.__data[self.level(key)].get(self.parse_key(key), default)

    def data(self):
        return self.__data

class ComboCounter:

    def __init__(self, names2d: tuple[tuple[str,...],...], *, k:int):

        # Quick linting needed?
        self.names2d = names2d
        self.__k = k
        self.cc_dict = ComboCounterDict(k=k)

    def __setitem__(self, key, value: int) -> None:
        self.cc_dict[key] = value
        return

    def __getitem__(self, key) -> int:
        return self.cc_dict[key]

    def get(self, key, default=0):
        return self.cc_dict.get(key, default)

    def run(self):
        # Sometimes not going to run, instead will use iteratively
        for names in self.names2d:

            for name in names:
                self.cc_dict[name] = self.cc_dict.get(name, 0) + 1

            for k in range(2, self.__k+1):

                for combo in [tuple(combo_) for combo_ in itertools.combinations(names, k)]:
                    self.cc_dict[combo] = self.cc_dict.get(combo, 0) + 1

    def counts(self, percents=False):


        if percents:
            if hasattr(self, 'sorted_percents'):
                return self.sorted_percents

            self.sorted = {
                level: dict(sorted(
                    {k: v for k,v in innerdict.items()}.items(),
                    key=lambda item: item[1],
                    reverse=True
                ))
                for level, innerdict in self.cc_dict.data().items()
            }

            n_lineups = len(self.names2d)

            self.sorted_percents = {
                level: {
                    combo: round(100*count/n_lineups, 2)
                    for combo, count in combo_count.items()
                }
                for level, combo_count in self.sorted.items()
            }

            return self.sorted_percents

        if hasattr(self, 'sorted'):
            return self.sorted

        # Don't want to have to sort every time it is called
        # Three dictcomps in one (with a fourth built-into an equation!) --> pretty dope
        self.sorted = {
            level: dict(sorted(
                {k: v for k,v in innerdict.items() if v > {3:0,4:0}.get(level,0)}.items(),
                key=lambda item: item[1],
                reverse=True
            ))
            for level, innerdict in self.cc_dict.data().items()
        }

        return self.sorted

    def player_exposure_at_level(self, name: str, level: int):
        if level == 1:
            return {name_: count_ for name_, count_ in self.counts()[level].items() if name == name_}

        return {combo_: count_ for combo_, count_ in self.counts()[level].items() if name in combo_}

    def handcuffs(self, name: str, **kwargs):

        # Going to start with just first level and then add to same dictionary for each subsequent level
        # Analagous to functools.reduce, except with { **{}, **{} } to combine two dicts into one.
        exposures = self.player_exposure_at_level(name, 1)
        for level in range(2, self.__k+1):
            exposures = {
                **exposures,
                **self.player_exposure_at_level(name, level)
            }

        exposures = {k: v for k,v in exposures.items() if v > kwargs.get('cutoff', max(exposures.values()) / 2)}

        return exposures
