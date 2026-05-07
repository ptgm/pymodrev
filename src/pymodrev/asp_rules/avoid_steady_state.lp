%generate
1{vlabel(P,0,V,S):sign(S)}1 :- vertex(V), exp(P,not_ss).
1{vlabel(P,1,V,S):sign(S)}1 :- vertex(V), exp(P,not_ss).
1{update(P,0,V):vertex(V)}1 :- exp(P,not_ss).

:-vlabel(P,0,V,S1), obs_vlabel(P,V,S2),complement(S1,S2).


% functions
% one positive or negative contribution in a clause
onePositive(P,V,Id) :- functionAnd(V,Id, V2), edge(V2,V,S), vlabel(P,0,V2,S), exp(P,not_ss), update(P,0,V).
oneNegative(P,V,Id) :- functionAnd(V,Id, V2), edge(V2,V,S), vlabel(P,0,V2,T), complement(S,T), exp(P,not_ss), update(P,0,V).

% none positive or none negative on a clause
% nonePositive(V,Id) :- not onePositive(V,Id), oneNegative(V,Id).
noneNegative(P,V,Id) :- onePositive(P,V,Id), not oneNegative(P,V,Id), exp(P,not_ss), update(P,0,V).

vlabel(P,1,V,1) :- 1{noneNegative(P,V,Id):functionOr(V,Id)}, vertex(V), exp(P,not_ss), not r_part(V), update(P,0,V).
vlabel(P,1,V,0) :- {noneNegative(P,V,Id):functionOr(V,Id)}0, vertex(V), exp(P,not_ss), functionOr(V,_), not r_gen(V), update(P,0,V).

%keep all others
vlabel(P,1,V,S) :- not update(P,0,V), vlabel(P,0,V,S), exp(P,not_ss).

%at least one value must change for the given state not to be a steady state
%:- {vlabel(P,1,V,S1):vlabel(P,0,V,S2),vertex(V),S1!=S2}0, exp(P,not_ss).
:- update(P,0,V), exp(P,not_ss), vlabel(P,0,V,S), vlabel(P,1,V,S). 

#show vlabel/4.
#show update/3.

% show inconsistent nodes per experiments
inc(P,V) :- vlabel(P,1,V,0), 1{noneNegative(P,V,Id):functionOr(V,Id)}, vertex(V), exp(P,not_ss), r_part(V), update(P,0,V).
inc(P,V) :- vlabel(P,1,V,1), {noneNegative(P,V ,Id):functionOr(V,Id)}0, vertex(V), exp(P,not_ss), functionOr(V,_), r_gen(V),update(P,0,V).
#show inc/2.
