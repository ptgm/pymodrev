% assign final state time step
% obs_named_vlabel(Exp,Name,Node,Value) define the final state observed
% max_time(Exp, Time) defines the maximum time step

% Optional fixed bound injected from Python for iterative deepening.
finalStateTime(P,T) :- reach_bound(P,T), obs_named_vlabel(P,final,_,_).

1{finalStateTime(P,T): T = 1..T2, max_time(P,T2)}1 :- obs_named_vlabel(P,final,_,_), not reach_bound(P,_).
obs_vlabel(P,T,V,S) :- obs_named_vlabel(P,final,V,S), finalStateTime(P,T).

#show finalStateTime/2.
%#show obs_vlabel/4.
