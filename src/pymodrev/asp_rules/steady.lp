%guarantee of stable state observation
%ss(P) :- exp(P), not time(P,_), not exp(P,not_ss).
%the above was replaced by exp(P,steady)

%generate
1{vlabel(P,V,S):sign(S)}1 :- vertex(V), exp(P,steady).

:-vlabel(P,V,S1), obs_vlabel(P,V,S2),complement(S1,S2).

% functions
% one positive or negative contribution in a clause
onePositive(P,V,Id) :- functionAnd(V,Id, V2), edge(V2,V,S), vlabel(P,V2,S), exp(P,steady).
oneNegative(P,V,Id) :- functionAnd(V,Id, V2), edge(V2,V,S), vlabel(P,V2,T), complement(S,T), exp(P,steady).

% none positive or none negative on a clause
% nonePositive(V,Id) :- not onePositive(V,Id), oneNegative(V,Id).
noneNegative(P,V,Id) :- onePositive(P,V,Id), not oneNegative(P,V,Id), exp(P,steady).

vlabel(P,V,1) :- 1{noneNegative(P,V,Id):functionOr(V,Id)}, vertex(V), exp(P,steady), not r_part(V).
vlabel(P,V,0) :- {noneNegative(P,V,Id):functionOr(V,Id)}0, vertex(V), exp(P,steady), functionOr(V,_), not r_gen(V).

#show vlabel/3.

% show inconsistent nodes per experiments
inc(P,V) :- vlabel(P,V,0), 1{noneNegative(P,V,Id):functionOr(V,Id)}, vertex(V), exp(P,steady), r_part(V).
inc(P,V) :- vlabel(P,V,1), {noneNegative(P,V ,Id):functionOr(V,Id)}0, vertex(V), exp(P,steady), functionOr(V,_), r_gen(V).
#show inc/2.
