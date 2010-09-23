# Copyright (C) 1996-2010 Power System Engineering Research Center
# Copyright (C) 2010 Richard Lincoln
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from numpy import array, nonzero, ones, zeros, r_
from scipy.sparse import csr_matrix

from idx_cost import MODEL, POLYNOMIAL

from totcost import totcost
from polycost import polycost

def opf_costfcn(x, om, *args):
    """Evaluates objective function, gradient and Hessian for OPF.

    Objective function evaluation routine for AC optimal power flow,
    suitable for use with MIPS or FMINCON. Computes objective function value,
    gradient and Hessian.

    @type x: array
    @param x: optimization vector
    @type om: opf_model
    @param om: OPF model object

    @return:
      F   : value of objective function
      DF  : (optional) gradient of objective function (column vector)
      D2F : (optional) Hessian of objective function (sparse matrix)

    @see: L{opf_consfcn}, L{opf_hessfcn}
    """
    ##----- initialize -----
    ## unpack data
    mpc = om.get_mpc()
    baseMVA, gen, gencost = mpc["baseMVA"], mpc["gen"], mpc["gencost"]
    cp = om.get_cost_params()
    N, Cw, H, dd, rh, kk, mm = \
        cp["N"], cp["Cw"], cp["H"], cp["dd"], cp["rh"], cp["kk"], cp["mm"]
    vv = om.get_idx()

    ## problem dimensions
    ng = gen.shape[0]          ## number of dispatchable injections
    ny = om.getN('var', 'y')   ## number of piece-wise linear costs
    nxyz = len(x)              ## total number of control vars of all types

    ## grab Pg & Qg
    Pg = x[vv["i1"]["Pg"]:vv["iN"]["Pg"]]  ## active generation in p.u.
    Qg = x[vv["i1"]["Qg"]:vv["iN"]["Qg"]]  ## reactive generation in p.u.

    ##----- evaluate objective function -----
    ## polynomial cost of P and Q
    # use totcost only on polynomial cost in the minimization problem
    # formulation, pwl cost is the sum of the y variables.
    ipol = nonzero(gencost[:, MODEL] == POLYNOMIAL)   ## poly MW and MVAr costs
    xx = r_[ Pg, Qg ] * baseMVA
    if any(ipol):
        f = sum( totcost(gencost[ipol, :], xx[ipol]) )  ## cost of poly P or Q
    else:
        f = 0

    ## piecewise linear cost of P and Q
    if ny > 0:
        ccost = csr_matrix((ones(1,ny),
                            (ones((1,ny)),
                             range(vv["i1"]["y"], vv["iN"]["y"]))),
                            (1, nxyz)).todense()
        f = f + ccost * x
    else:
        ccost = zeros((1, nxyz))

    ## generalized cost term
    if any(N):
        nw = N.shape[0]
        r = N * x - rh                  ## Nx - rhat
        iLT = nonzero(r < -kk)          ## below dead zone
        iEQ = nonzero(r == 0 & kk == 0) ## dead zone doesn't exist
        iGT = nonzero(r > kk)           ## above dead zone
        iND = r_[iLT, iEQ, iGT]         ## rows that are Not in the Dead region
        iL = nonzero(dd == 1)           ## rows using linear function
        iQ = nonzero(dd == 2)           ## rows using quadratic function
        LL = csr_matrix((1, (iL, iL)), (nw, nw))
        QQ = csr_matrix((1, (iQ, iQ)), (nw, nw))
        kbar = csr_matrix((r_[   ones((len(iLT), 1)),
                                zeros((len(iEQ), 1)),
                                -ones((len(iGT), 1))], (iND, iND)),
                                (nw, nw)) * kk
        rr = r + kbar                  ## apply non-dead zone shift
        M = csr_matrix((mm(iND), (iND, iND)), (nw, nw))  ## dead zone or scale
        diagrr = csr_matrix((rr, (range(nw), range(nw))), (nw, nw))

        ## linear rows multiplied by rr(i), quadratic rows by rr(i)^2
        w = M * (LL + QQ * diagrr) * rr

        f = f + (w.T * H * w) / 2 + Cw.T * w

    ##----- evaluate cost gradient -----
    ## index ranges
    iPg = range(vv["i1"]["Pg"], vv["iN"]["Pg"])
    iQg = range(vv["i1"]["Qg"], vv["iN"]["Qg"])

    ## polynomial cost of P and Q
    df_dPgQg = zeros(2 * ng)        ## w.r.t p.u. Pg and Qg
    df_dPgQg[ipol] = baseMVA * polycost(gencost[ipol, :], xx[ipol], 1)
    df = zeros(nxyz)
    df[iPg] = df_dPgQg[:ng]
    df[iQg] = df_dPgQg[ng:ng + ng]

    ## piecewise linear cost of P and Q
    df = df + ccost.T  # The linear cost row is additive wrt any nonlinear cost.

    ## generalized cost term
    if any(N):
        HwC = H * w + Cw
        AA = N.T * M * (LL + 2 * QQ * diagrr)
        df = df + AA * HwC

        ## numerical check
        if 0:    ## 1 to check, 0 to skip check
            ddff = zeros(df.shape)
            step = 1e-7
            tol  = 1e-3
            for k in range(len(x)):
                xx = x
                xx[k] = xx[k] + step
                ddff[k] = (opf_costfcn(xx, om) - f) / step
            if max(abs(ddff - df)) > tol:
                idx = nonzero(abs(ddff - df) == max(abs(ddff - df)))
                print 'Mismatch in gradient'
                print 'idx             df(num)         df              diff'
                print '%4d%16g%16g%16g' % \
                    (range(len(df)), ddff.T, df.T, abs(ddff - df).T)
                print 'MAX'
                print '%4d%16g%16g%16g' % \
                    (idx.T, ddff[idx].T, df[idx].T, abs(ddff[idx] - df[idx]).T)

    ## ---- evaluate cost Hessian -----
    pcost = gencost[range(ng), :]
    if gencost.shape[0] > ng:
        qcost = gencost[ng + 1:2 * ng, :]
    else:
        qcost = array([])

    ## polynomial generator costs
    d2f_dPg2 = csr_matrix((ng, 1))               ## w.r.t. p.u. Pg
    d2f_dQg2 = csr_matrix((ng, 1))               ## w.r.t. p.u. Qg
    ipolp = nonzero(pcost[:, MODEL] == POLYNOMIAL)
    d2f_dPg2[ipolp] = \
            baseMVA**2 * polycost(pcost[ipolp, :], Pg[ipolp]*baseMVA, 2)
    if any(qcost):          ## Qg is not free
        ipolq = nonzero(qcost[:, MODEL] == POLYNOMIAL)
        d2f_dQg2[ipolq] = \
                baseMVA**2 * polycost(qcost[ipolq, :], Qg[ipolq] * baseMVA, 2)
    i = r_[iPg, iQg].T
    d2f = csr_matrix((r_[d2f_dPg2, d2f_dQg2], (i, i)), (nxyz, nxyz))

    ## generalized cost
    if any(N):
        d2f = d2f + AA * H * AA.T + 2 * N.T * M * QQ * \
                csr_matrix((HwC, (range(nw), range(nw))), (nw, nw)) * N

    return f, df, d2f